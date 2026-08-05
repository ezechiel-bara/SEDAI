import 'dart:convert';

/// Un diagnostic sauvegardé dans l'historique local de l'application.
class DiagnosisRecord {
  final String   id;
  final String   content;
  final String   vehicleMarque;
  final String   vehicleModele;
  final String   vehicleMoteur;
  final DateTime timestamp;

  DiagnosisRecord({
    required this.id,
    required this.content,
    required this.vehicleMarque,
    required this.vehicleModele,
    required this.vehicleMoteur,
    required this.timestamp,
  });

  /// Résumé court pour les aperçus de liste (150 caractères max)
  String get preview {
    if (content.length <= 150) return content;
    return '${content.substring(0, 150).trimRight()}…';
  }

  String get vehicleLabel {
    final parts = [vehicleMarque, vehicleModele, vehicleMoteur]
        .where((s) => s.isNotEmpty)
        .toList();
    return parts.isEmpty ? 'Véhicule inconnu' : parts.join(' · ');
  }

  // ---------- Sérialisation ----------

  Map<String, dynamic> toJson() => {
    'id':            id,
    'content':       content,
    'vehicleMarque': vehicleMarque,
    'vehicleModele': vehicleModele,
    'vehicleMoteur': vehicleMoteur,
    'timestamp':     timestamp.toIso8601String(),
  };

  factory DiagnosisRecord.fromJson(Map<String, dynamic> json) {
    return DiagnosisRecord(
      id:            json['id']            as String? ?? '',
      content:       json['content']       as String? ?? '',
      vehicleMarque: json['vehicleMarque'] as String? ?? '',
      vehicleModele: json['vehicleModele'] as String? ?? '',
      vehicleMoteur: json['vehicleMoteur'] as String? ?? '',
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ?? DateTime.now(),
    );
  }

  static List<DiagnosisRecord> listFromJson(String jsonString) {
    final List<dynamic> list = jsonDecode(jsonString) as List<dynamic>;
    return list
        .map((e) => DiagnosisRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  static String listToJson(List<DiagnosisRecord> records) {
    return jsonEncode(records.map((r) => r.toJson()).toList());
  }
}
