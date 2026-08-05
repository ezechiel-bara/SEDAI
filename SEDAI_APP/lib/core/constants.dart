import 'package:flutter/material.dart';

class AppColors {
  // Backgrounds
  static const Color background = Color(0xFF070D18);
  static const Color surface = Color(0xFF0E1A2E);
  static const Color surfaceAlt = Color(0xFF152035);
  static const Color cardBorder = Color(0xFF1C2F4A);

  // Accents
  static const Color accentCyan = Color(0xFF00D4FF);
  static const Color accentGreen = Color(0xFF00E5A0);
  static const Color accentBlue = Color(0xFF3B82F6);

  // States
  static const Color alertOrange = Color(0xFFFF8C00);
  static const Color dangerRed = Color(0xFFFF3535);
  static const Color successGreen = Color(0xFF22C55E);

  // Text
  static const Color textPrimary = Color(0xFFE8F0FE);
  static const Color textSecondary = Color(0xFF5A7A9A);
  static const Color textMuted = Color(0xFF2E4060);
}

class AppConstants {
  static const String appTitle = 'SEDAI';
  static const String appSubtitle = 'DIAGNOSTIC INTELLIGENT';

  // Storage keys
  static const String keyIp = 'server_ip';
  static const String keyPort = 'server_port';
  static const String keySetupDone = 'setup_done';
  static const String keyVehicleMarque = 'vehicle_marque';
  static const String keyVehicleModele = 'vehicle_modele';
  static const String keyVehicleMoteur =
      'vehicle_moteur'; // type : 1.8L essence
  static const String keyVehicleModMoteur =
      'vehicle_mod_moteur'; // modèle : 1ZZ-FE
  static const String keyVehicleYear = 'vehicle_year';
  static const String keyVehicleVin = 'vehicle_vin';
  static const String keyVehicleTransmission = 'vehicle_transmission';
  static const String keyVehicleFuelType = 'vehicle_fuel_type';
  static const String keyVehicleCylinders = 'vehicle_cylinders';
  static const String keyVehicleDisplacement = 'vehicle_displacement';
  static const String keyHistory = 'diagnosis_history';

  // Defaults
  static const String defaultIp = '192.168.4.1';
  static const String defaultPort = '8765';

  // Limits
  static const int maxHistoryEntries = 50;
}
