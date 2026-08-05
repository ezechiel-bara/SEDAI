class VehicleData {
  final double vitesse;
  final double regime;
  final double tempMoteur;
  final double maf;
  final double lambda;
  final double batterie;
  final double pressionMap;
  final double pressionHuile;
  
  // Nouveaux PIDs étendus
  final double tempTransmission;
  final double stftB1;
  final double ltftB1;
  final double pressionCarburant;
  final double niveauCarburant;
  final String statutObd;

  VehicleData({
    this.vitesse = 0,
    this.regime = 0,
    this.tempMoteur = 0,
    this.maf = 0,
    this.lambda = 1.0,
    this.batterie = 12.0,
    this.pressionMap = 0,
    this.pressionHuile = 0,
    this.tempTransmission = 0,
    this.stftB1 = 0,
    this.ltftB1 = 0,
    this.pressionCarburant = 0,
    this.niveauCarburant = 0,
    this.statutObd = 'Déconnecté',
  });

  factory VehicleData.fromJson(Map<String, dynamic> json) {
    try {
      return VehicleData(
        vitesse:           _parseNum(json['SPEED'] ?? json['vitesse'], 0),
        regime:            _parseNum(json['RPM'] ?? json['regime'], 0),
        tempMoteur:        _parseNum(json['COOLANT_TEMP'] ?? json['temp_moteur'], 0),
        maf:               _parseNum(json['MAF'] ?? json['maf'], 0),
        lambda:            _parseNum(json['O2_B1S1'] ?? json['lambda'], 1.0),
        batterie:          _parseNum(json['CONTROL_MODULE_VOLTAGE'] ?? json['batterie'], 12.0),
        pressionMap:       _parseNum(json['INTAKE_PRESSURE'] ?? json['pression_map'], 0),
        pressionHuile:     _parseNum(json['OIL_PRESSURE'] ?? json['pression_huile'], 0),
        tempTransmission:  _parseNum(json['temp_transmission'], 0),
        stftB1:            _parseNum(json['SHORT_TERM_FUEL_TRIM_1'] ?? json['stft_b1'], 0),
        ltftB1:            _parseNum(json['LONG_TERM_FUEL_TRIM_1'] ?? json['ltft_b1'], 0),
        pressionCarburant: _parseNum(json['FUEL_PRESSURE'] ?? json['pression_carburant'], 0),
        niveauCarburant:   _parseNum(json['FUEL_LEVEL'] ?? json['niveau_carburant'], 0),
        statutObd:         json['statut_obd']?.toString() ?? 'Déconnecté',
      );
    } catch (e) {
      return VehicleData.initial();
    }
  }

  static double _parseNum(dynamic v, double fallback) {
    if (v == null) return fallback;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? fallback;
    return fallback;
  }

  factory VehicleData.initial() => VehicleData();
}

/// Résultat brut reçu depuis le Raspberry Pi (non encore sauvegardé)
class DiagnosisResult {
  final String content;
  final DateTime timestamp;
  final List<String> imageUrls;
  final List<Map<String, dynamic>> technicalSheets;

  DiagnosisResult({
    required this.content,
    required this.timestamp,
    this.imageUrls = const [],
    this.technicalSheets = const [],
  });

  factory DiagnosisResult.fromJson(Map<String, dynamic> json) {
    return DiagnosisResult(
      content:   json['payload']?['text'] ?? json['content'] ?? '',
      timestamp: DateTime.now(),
      imageUrls: (json['image_urls'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      technicalSheets: (json['technical_sheets'] as List<dynamic>?)?.map((e) => e as Map<String, dynamic>).toList() ?? [],
    );
  }
}
