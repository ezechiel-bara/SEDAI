import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/vehicle_data.dart';
import 'storage_service.dart';

enum ConnectionStatus { disconnected, connecting, connected, error }

class WebSocketService {
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;

  static const _notificationChannel =
      MethodChannel('com.autojapan.sedai/notifications');

  // Cooldowns pour éviter de spammer les notifications
  DateTime? _lastTempWarning;
  DateTime? _lastBatteryWarning;
  DateTime? _lastFuelWarning;
  DateTime? _lastMapWarning;

  final _dataController = StreamController<VehicleData>.broadcast();
  final _diagnosisController = StreamController<DiagnosisResult>.broadcast();
  final _statusController = StreamController<ConnectionStatus>.broadcast();
  final _chatController = StreamController<Map<String, dynamic>>.broadcast();
  final _transcriptionController = StreamController<String>.broadcast();

  Stream<VehicleData> get dataStream => _dataController.stream;
  Stream<DiagnosisResult> get diagnosisStream => _diagnosisController.stream;
  Stream<ConnectionStatus> get statusStream => _statusController.stream;
  Stream<Map<String, dynamic>> get chatStream => _chatController.stream;
  Stream<String> get transcriptionStream => _transcriptionController.stream;

  ConnectionStatus _currentStatus = ConnectionStatus.disconnected;
  ConnectionStatus get currentStatus => _currentStatus;

  bool _isManualDisconnect = false;

  bool _isConnecting = false;

  // ── Connexion ─────────────────────────────────────────────────────────────
  void connect() {
    _reconnectTimer?.cancel();
    if (_isConnecting || _isManualDisconnect) return;
    _isConnecting = true;

    final ip = StorageService.getServerIp().trim();
    final port = StorageService.getServerPort().trim();

    if (ip.isEmpty || port.isEmpty) {
      _isConnecting = false;
      _setStatus(ConnectionStatus.error);
      return;
    }

    // Fermeture de toute session précédente pour éviter les fuites
    _channel?.sink.close();

    final url = 'ws://$ip:$port';
    _setStatus(ConnectionStatus.connecting);

    final uri = Uri.tryParse(url);
    if (uri == null) {
      _isConnecting = false;
      _handleError('URI invalide : $url');
      return;
    }

    _connectToChannel(uri);
  }

  Future<void> _connectToChannel(Uri uri) async {
    try {
      final channel = WebSocketChannel.connect(uri);

      if (_isManualDisconnect) {
        channel.sink.close();
        _isConnecting = false;
        return;
      }

      _channel?.sink.close();
      _channel = channel;

      _channel!.stream.listen(
        (message) {
          // Confirme la connexion dès le 1er message reçu du Raspberry Pi
          if (_currentStatus != ConnectionStatus.connected) {
            _setStatus(ConnectionStatus.connected);
            sendVehicleInfo(); // Envoie la config véhicule une fois connecté
          }
          _isConnecting = false;
          _handleMessage(message);
        },
        onError: (error) {
          _isConnecting = false;
          debugPrint("[WS] Erreur réseau : $error");
          _handleError(error);
        },
        onDone: () {
          _isConnecting = false;
          _handleDone();
        },
        cancelOnError: true,
      );

      // NOTE: setStatus(connected) et sendVehicleInfo() sont maintenant déclenchés
      // par le 1er message reçu, pas ici, pour éviter un faux positif de connexion.
    } catch (e) {
      _isConnecting = false;
      _handleError(e);
    }
  }

  void disconnect() {
    _isManualDisconnect = true;
    _channel?.sink.close();
    _setStatus(ConnectionStatus.disconnected);
  }

  void reconnect() {
    disconnect();
    Future.delayed(const Duration(milliseconds: 300), () {
      _isManualDisconnect = false;
      connect();
    });
  }

  // ── Actions envoyées au Raspberry Pi ─────────────────────────────────────

  /// Envoie la configuration du véhicule pour adapter l'IA et les seuils
  void sendVehicleInfo() {
    _sendMessage({
      'action': 'vehicle_info',
      'data': _vehiclePayload(),
    });
  }

  /// Déclenche un diagnostic IA complet
  void requestDiagnostic() {
    sendVehicleInfo(); // Assure que le Pi a la config la plus récente avant l'analyse
    _sendMessage({
      'action': 'diagnose',
    });
  }

  /// Démarre l'écoute du microphone USB sur le Raspberry Pi
  void activateVoice() {
    _sendMessage({
      'action': 'voice_activate',
    });
  }

  /// Arrête l'écoute du microphone USB
  void deactivateVoice() {
    _sendMessage({'action': 'voice_deactivate'});
  }

  /// Change le volume global du haut-parleur (Raspberry Pi)
  void setVolume(double level) {
    _sendMessage({
      'action': 'set_volume',
      'level': level.toInt(),
    });
  }

  /// Envoie un message textuel au chat IA
  void sendChatMessage(String text) {
    _sendMessage({
      'action': 'chat_message',
      'text': text,
    });
  }

  String? _lastReport;

  // ── Gestion des messages reçus ────────────────────────────────────────────
  void _handleMessage(dynamic message) {
    // Protection : ignorer les frames binaires envoyées par erreur
    if (message is! String) {
      debugPrint('[WS] Frame binaire ignorée (type: ${message.runtimeType})');
      return;
    }
    try {
      final Map<String, dynamic> json = jsonDecode(message);

      // Le Raspberry Pi envoie les PIDs dans un objet plat (ex: "SPEED": 50)
      // On l'envoie systèmatiquement pour mettre à jour les jauges
      final data = VehicleData.fromJson(json);
      _dataController.add(data);

      // Vérification et déclenchement des notifications d'alertes locales
      _checkAndTriggerNotifications(data);

      // Gestion du rapport d'analyse
      // On vérifie s'il y a un rapport, s'il n'est pas vide et s'il est différent du précédent
      if (json.containsKey('rapport')) {
        final text = json['rapport'] as String;
        if (text.isNotEmpty && text != _lastReport) {
          _lastReport = text;
          _diagnosisController
              .add(DiagnosisResult(content: text, timestamp: DateTime.now()));
        }
      }

      // Gestion du chat textuel
      if (json.containsKey('chat')) {
        final chatData = json['chat'] as Map<String, dynamic>;
        _chatController.add(chatData);
      }

      // Gestion de la transcription
      if (json.containsKey('transcription')) {
        final trans = json['transcription'] as String;
        _transcriptionController.add(trans);
      }
    } catch (e) {
      // Erreur de parsing silencieuse
    }
  }

  void _checkAndTriggerNotifications(VehicleData data) {
    // Ne rien faire si l'OBD-II n'est pas connecté
    final isConnected = data.statutObd.toLowerCase().contains('connecté') &&
        !data.statutObd.toLowerCase().contains('déconnecté');
    if (!isConnected) return;

    final now = DateTime.now();

    // 1. Surchauffe Moteur
    if (data.tempMoteur >= 100) {
      if (_lastTempWarning == null ||
          now.difference(_lastTempWarning!) > const Duration(minutes: 2)) {
        _lastTempWarning = now;
        _showNativeNotification(
          "🚨 ALERTE CRITIQUE : Surchauffe Moteur",
          "La température du liquide de refroidissement est de ${data.tempMoteur}°C. Arrêtez le véhicule dès que possible !",
        );
      }
    }

    // 2. Tension Batterie Basse
    if (data.batterie < 11.5) {
      if (_lastBatteryWarning == null ||
          now.difference(_lastBatteryWarning!) > const Duration(minutes: 2)) {
        _lastBatteryWarning = now;
        _showNativeNotification(
          "⚠️ ALERTE BATTERIE : Tension Faible",
          "La tension de la batterie est de ${data.batterie}V. Risque de panne d'alternateur ou de batterie déchargée.",
        );
      }
    }

    // 3. Niveau Carburant Critique
    if (data.niveauCarburant > 0 && data.niveauCarburant <= 10) {
      if (_lastFuelWarning == null ||
          now.difference(_lastFuelWarning!) > const Duration(minutes: 5)) {
        _lastFuelWarning = now;
        _showNativeNotification(
          "⛽ ALERTE CARBURANT : Niveau Critique",
          "Le réservoir est presque vide (${data.niveauCarburant.toStringAsFixed(1)}%). Veuillez faire le plein rapidement.",
        );
      }
    }

    // 4. Surpression Admission MAP
    if (data.pressionMap >= 200) {
      if (_lastMapWarning == null ||
          now.difference(_lastMapWarning!) > const Duration(minutes: 2)) {
        _lastMapWarning = now;
        _showNativeNotification(
          "🚨 ALERTE MOTEUR : Surpression Admission",
          "La pression d'admission MAP est de ${data.pressionMap} kPa (risque pour le turbocompresseur).",
        );
      }
    }
  }

  Future<void> _showNativeNotification(String title, String body) async {
    try {
      await _notificationChannel.invokeMethod('showNotification', {
        'title': title,
        'body': body,
      });
    } catch (e) {
      debugPrint("[WS] Échec de l'envoi de la notification native : $e");
    }
  }

  void _handleError(dynamic error) {
    _setStatus(ConnectionStatus.error);
    _scheduleReconnect();
  }

  void _handleDone() {
    if (!_isManualDisconnect) {
      _setStatus(ConnectionStatus.disconnected);
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    if (_isManualDisconnect) return;

    _reconnectTimer = Timer(const Duration(seconds: 5), () {
      connect();
    });
  }

  // ── Utilitaires ───────────────────────────────────────────────────────────
  void _sendMessage(Map<String, dynamic> data) {
    if (_channel != null && _currentStatus == ConnectionStatus.connected) {
      try {
        _channel!.sink.add(jsonEncode(data));
      } catch (e) {
        debugPrint("[WS] Erreur envoi : $e");
      }
    }
  }

  /// Payload véhicule complet envoyé à l'IA à chaque requête
  Map<String, String> _vehiclePayload() => {
        'marque': StorageService.getVehicleMarque(),
        'modele': StorageService.getVehicleModele(),
        'annee': StorageService.getVehicleYear(),
        'modele_moteur': StorageService
            .getVehicleModMoteur(), // Mappé sur modele_moteur pour le Pi
        'type_moteur':
            '${StorageService.getVehicleMoteur()} ${StorageService.getVehicleFuelType()}'
                .trim(),
        'type_transmission': StorageService.getVehicleTransmission(),
      };

  void _setStatus(ConnectionStatus status) {
    _currentStatus = status;
    _statusController.add(status);
  }

  void dispose() {
    _reconnectTimer?.cancel();
    disconnect();
    _dataController.close();
    _diagnosisController.close();
    _statusController.close();
    _chatController.close();
    _transcriptionController.close();
  }
}
