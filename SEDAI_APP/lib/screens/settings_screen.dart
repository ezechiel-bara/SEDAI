import 'package:flutter/material.dart';
import '../core/constants.dart';
import '../services/storage_service.dart';
import '../services/websocket_service.dart';

class SettingsScreen extends StatefulWidget {
  final WebSocketService wsService;
  final VoidCallback onSettingsSaved;

  const SettingsScreen({
    super.key,
    required this.wsService,
    required this.onSettingsSaved,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _ipCtrl;
  late final TextEditingController _portCtrl;
  late final TextEditingController _marqueCtrl;
  late final TextEditingController _modeleCtrl;
  late final TextEditingController _modMoteurCtrl;
  late final TextEditingController _typeMoteurCtrl;
  late final TextEditingController _anneeCtrl;
  late final TextEditingController _transmissionCtrl;

  bool _saving = false;
  late double _volumeLevel;

  @override
  void initState() {
    super.initState();
    _volumeLevel = StorageService.getVolume();
    _ipCtrl = TextEditingController(text: StorageService.getServerIp());
    _portCtrl = TextEditingController(text: StorageService.getServerPort());
    _marqueCtrl =
        TextEditingController(text: StorageService.getVehicleMarque());
    _modeleCtrl =
        TextEditingController(text: StorageService.getVehicleModele());
    _modMoteurCtrl =
        TextEditingController(text: StorageService.getVehicleModMoteur());
    _typeMoteurCtrl =
        TextEditingController(text: StorageService.getVehicleMoteur());
    _anneeCtrl = 
        TextEditingController(text: StorageService.getVehicleYear());
    _transmissionCtrl = 
        TextEditingController(text: StorageService.getVehicleTransmission());
  }

  @override
  void dispose() {
    _ipCtrl.dispose();
    _portCtrl.dispose();
    _marqueCtrl.dispose();
    _modeleCtrl.dispose();
    _modMoteurCtrl.dispose();
    _typeMoteurCtrl.dispose();
    _anneeCtrl.dispose();
    _transmissionCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);

    await StorageService.saveConnectionSettings(
      _ipCtrl.text.trim(),
      _portCtrl.text.trim(),
    );
    await StorageService.saveVehicleInfo(
      _marqueCtrl.text.trim(),
      _modeleCtrl.text.trim(),
      _typeMoteurCtrl.text.trim(),
      _modMoteurCtrl.text.trim(),
      _anneeCtrl.text.trim(),
      '',
      _transmissionCtrl.text.trim(),
      '',
      '',
      '',
    );

    widget.wsService.reconnect();
    widget.onSettingsSaved();
    setState(() => _saving = false);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.check_circle_outline,
                  color: AppColors.accentGreen, size: 18),
              SizedBox(width: 10),
              Text('Paramètres enregistrés. Reconnexion en cours…',
                  style: TextStyle(color: AppColors.textPrimary)),
            ],
          ),
          backgroundColor: AppColors.surface,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 40),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Connexion ─────────────────────────────────────────────────
            _sectionHeader(Icons.wifi_outlined, 'CONNEXION RASPBERRY PI'),
            const SizedBox(height: 14),
            _field(
              controller: _ipCtrl,
              label: 'Adresse IP',
              hint: '192.168.4.1',
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'IP requise' : null,
            ),
            const SizedBox(height: 12),
            _field(
              controller: _portCtrl,
              label: 'Port WebSocket',
              hint: '8765',
              keyboardType: TextInputType.number,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Port requis';
                final p = int.tryParse(v.trim());
                if (p == null || p < 1 || p > 65535) {
                  return 'Port invalide (1 – 65535)';
                }
                return null;
              },
            ),

            const SizedBox(height: 30),
            
            // ── Matériel ─────────────────────────────────────────────────
            _sectionHeader(Icons.speaker_outlined, 'MATÉRIEL DU VÉHICULE'),
            const SizedBox(height: 6),
            const Text(
              'Ajustez le volume physique du haut-parleur SEDAI.',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                const Icon(Icons.volume_down, color: AppColors.textSecondary, size: 20),
                Expanded(
                  child: Slider(
                    value: _volumeLevel,
                    min: 0,
                    max: 100,
                    divisions: 20,
                    activeColor: AppColors.accentCyan,
                    inactiveColor: AppColors.textSecondary.withValues(alpha: 0.3),
                    label: '${_volumeLevel.round()}%',
                    onChanged: (val) {
                      setState(() => _volumeLevel = val);
                    },
                    onChangeEnd: (val) {
                      StorageService.saveVolume(val);
                      if (widget.wsService.currentStatus == ConnectionStatus.connected) {
                        widget.wsService.setVolume(val);
                      }
                    },
                  ),
                ),
                const Icon(Icons.volume_up, color: AppColors.accentCyan, size: 20),
              ],
            ),

            const SizedBox(height: 30),

            // ── Véhicule ──────────────────────────────────────────────────
            _sectionHeader(
                Icons.directions_car_outlined, 'INFORMATIONS VÉHICULE'),
            const SizedBox(height: 6),
            const Text(
              'Transmises à l\'IA pour contextualiser les diagnostics.',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 14),
            _field(
              controller: _marqueCtrl,
              label: 'Marque',
              hint: 'Ex : Toyota, Honda, Suzuki…',
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Marque requise' : null,
            ),
            const SizedBox(height: 12),
            _field(
              controller: _modeleCtrl,
              label: 'Modèle du véhicule',
              hint: 'Ex : Corolla, CR-V, Swift…',
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Modèle requis' : null,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _field(
                    controller: _anneeCtrl,
                    label: 'Année',
                    hint: 'Ex: 2018',
                    keyboardType: TextInputType.number,
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Détail requis' : null,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: _field(
                    controller: _transmissionCtrl,
                    label: 'Transmission',
                    hint: 'Manuelle, Auto...',
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Détail requis' : null,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),

            // Sous-section moteur
            const Text(
              'MOTEUR',
              style: TextStyle(
                color: AppColors.accentCyan,
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 2.0,
              ),
            ),
            const SizedBox(height: 12),
            _field(
              controller: _modMoteurCtrl,
              label: 'Modèle du moteur',
              hint: 'Ex : 1ZZ-FE, K20A, OM651…',
              validator: (v) => (v == null || v.trim().isEmpty)
                  ? 'Modèle du moteur requis'
                  : null,
            ),
            const SizedBox(height: 12),
            _field(
              controller: _typeMoteurCtrl,
              label: 'Type de moteur',
              hint: 'Ex : 1.8L essence, 2.0L diesel turbo…',
              validator: (v) => (v == null || v.trim().isEmpty)
                  ? 'Type de moteur requis'
                  : null,
            ),

            const SizedBox(height: 32),

            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: _saving ? null : _save,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.accentCyan,
                  foregroundColor: AppColors.background,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10)),
                ),
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.background,
                        ),
                      )
                    : const Text(
                        'ENREGISTRER ET RECONNECTER',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.5,
                        ),
                      ),
              ),
            ),

            const SizedBox(height: 32),
            const Divider(),
            const SizedBox(height: 20),

            // ── À propos ──────────────────────────────────────────────────
            _sectionHeader(Icons.info_outline, 'À PROPOS'),
            const SizedBox(height: 14),
            _aboutRow('Application', 'SEDAI v2.0'),
            _aboutRow('Signification',
                'Système Embarqué de Diagnostic\nAutomobile Intelligent'),
            _aboutRow('Modèles IA', 'Phi-3 Mini 3.8B · Gemma3 4B (Q4_K_M)'),
            _aboutRow('Moteur ASR', 'Vosk (fr_FR-small, ~50 Mo)'),
            _aboutRow('Moteur TTS', 'Piper TTS (VITS/ONNX, hors ligne)'),
            _aboutRow('Protocole', 'OBD-II ELM327 via python-obd'),
            _aboutRow('Plateforme', 'Raspberry Pi 5 — 8 Go RAM'),
          ],
        ),
      ),
    );
  }

  Widget _sectionHeader(IconData icon, String text) {
    return Row(
      children: [
        Icon(icon, color: AppColors.accentCyan, size: 15),
        const SizedBox(width: 8),
        Text(
          text,
          style: const TextStyle(
            color: AppColors.accentCyan,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 2.0,
          ),
        ),
      ],
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required String hint,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      decoration: InputDecoration(labelText: label, hintText: hint),
      validator: validator,
    );
  }

  Widget _aboutRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label,
                style: const TextStyle(
                    color: AppColors.textSecondary, fontSize: 12)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}
