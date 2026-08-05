import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants.dart';
import '../models/diagnosis_record.dart';

class StorageService {
  static SharedPreferences? _prefs;

  static Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // ── Connexion ─────────────────────────────────────────────────────────────
  static String getServerIp() =>
      _prefs?.getString(AppConstants.keyIp) ?? AppConstants.defaultIp;
  static String getServerPort() =>
      _prefs?.getString(AppConstants.keyPort) ?? AppConstants.defaultPort;

  static Future<void> saveConnectionSettings(String ip, String port) async {
    await _prefs?.setString(AppConstants.keyIp, ip);
    await _prefs?.setString(AppConstants.keyPort, port);
  }

  // ── Paramètres matériels ──────────────────────────────────────────────────
  static double getVolume() =>
      _prefs?.getDouble('pref_volume') ?? 85.0;

  static Future<void> saveVolume(double volume) async {
    await _prefs?.setDouble('pref_volume', volume);
  }

  // ── Premier lancement ─────────────────────────────────────────────────────
  static bool isFirstLaunch() =>
      !(_prefs?.getBool(AppConstants.keySetupDone) ?? false);

  static Future<void> markSetupDone() async {
    await _prefs?.setBool(AppConstants.keySetupDone, true);
  }

  // ── Informations véhicule ─────────────────────────────────────────────────
  static String getVehicleMarque() =>
      _prefs?.getString(AppConstants.keyVehicleMarque) ?? '';
  static String getVehicleModele() =>
      _prefs?.getString(AppConstants.keyVehicleModele) ?? '';
  static String getVehicleMoteur() =>
      _prefs?.getString(AppConstants.keyVehicleMoteur) ?? '';
  static String getVehicleModMoteur() =>
      _prefs?.getString(AppConstants.keyVehicleModMoteur) ?? '';

  static String getVehicleYear() =>
      _prefs?.getString(AppConstants.keyVehicleYear) ?? '';
  static String getVehicleVin() =>
      _prefs?.getString(AppConstants.keyVehicleVin) ?? '';
  static String getVehicleTransmission() =>
      _prefs?.getString(AppConstants.keyVehicleTransmission) ?? 'Automatique';
  static String getVehicleFuelType() =>
      _prefs?.getString(AppConstants.keyVehicleFuelType) ?? 'Essence';
  static String getVehicleCylinders() =>
      _prefs?.getString(AppConstants.keyVehicleCylinders) ?? '';
  static String getVehicleDisplacement() =>
      _prefs?.getString(AppConstants.keyVehicleDisplacement) ?? '';

  static Future<void> saveVehicleInfo(
    String marque,
    String modele,
    String moteur,
    String modMoteur,
    String year,
    String vin,
    String transmission,
    String fuelType,
    String cylinders,
    String displacement,
  ) async {
    await _prefs?.setString(AppConstants.keyVehicleMarque, marque);
    await _prefs?.setString(AppConstants.keyVehicleModele, modele);
    await _prefs?.setString(AppConstants.keyVehicleMoteur, moteur);
    await _prefs?.setString(AppConstants.keyVehicleModMoteur, modMoteur);
    await _prefs?.setString(AppConstants.keyVehicleYear, year);
    await _prefs?.setString(AppConstants.keyVehicleVin, vin);
    await _prefs?.setString(AppConstants.keyVehicleTransmission, transmission);
    await _prefs?.setString(AppConstants.keyVehicleFuelType, fuelType);
    await _prefs?.setString(AppConstants.keyVehicleCylinders, cylinders);
    await _prefs?.setString(AppConstants.keyVehicleDisplacement, displacement);
  }

  // ── Historique des diagnostics ────────────────────────────────────────────
  static List<DiagnosisRecord> getHistory() {
    final jsonStr = _prefs?.getString(AppConstants.keyHistory);
    if (jsonStr == null || jsonStr.isEmpty) return [];
    try {
      return DiagnosisRecord.listFromJson(jsonStr);
    } catch (_) {
      return [];
    }
  }

  static Future<void> addRecord(DiagnosisRecord record) async {
    final records = getHistory();
    records.insert(0, record);
    if (records.length > AppConstants.maxHistoryEntries) {
      records.removeRange(AppConstants.maxHistoryEntries, records.length);
    }
    await _prefs?.setString(
      AppConstants.keyHistory,
      DiagnosisRecord.listToJson(records),
    );
  }

  static Future<void> deleteRecord(String id) async {
    final records = getHistory();
    records.removeWhere((r) => r.id == id);
    await _prefs?.setString(
      AppConstants.keyHistory,
      DiagnosisRecord.listToJson(records),
    );
  }

  static Future<void> clearHistory() async {
    await _prefs?.remove(AppConstants.keyHistory);
  }
}
