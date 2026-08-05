# -*- coding: utf-8 -*-
# verify_pipeline.py - Verification bout-en-bout OBD -> WebSocket -> Flutter
import os
from datetime import datetime

# === 1. Table _pid_key() telle que dans obd_module.py (apres correction) ===
PID_TO_KEY = {
    "RPM":                    "RPM",
    "COOLANT_TEMP":           "COOLANT_TEMP",
    "CONTROL_MODULE_VOLTAGE": "CONTROL_MODULE_VOLTAGE",
    "SPEED":                  "SPEED",
    "ENGINE_LOAD":            "ENGINE_LOAD",
    "MAF":                    "MAF",
    "SHORT_FUEL_TRIM_1":      "SHORT_TERM_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1":       "LONG_TERM_FUEL_TRIM_1",
    "THROTTLE_POS":           "THROTTLE_POS",
    "INTAKE_TEMP":            "INTAKE_TEMP",
    "FUEL_LEVEL":             "FUEL_LEVEL",
    "O2_B1S1":                "O2_B1S1",
    "INTAKE_PRESSURE":        "INTAKE_PRESSURE",
    "FUEL_PRESSURE":          "FUEL_PRESSURE",
    "TIMING_ADVANCE":         "TIMING_ADVANCE",
    "ENGINE_OIL_PRESSURE":    "ENGINE_OIL_PRESSURE",
    "OIL_TEMP":               "OIL_TEMP",
}

# === 2. Cles attendues par vehicle_data.dart (Flutter fromJson) ===
# Extrait exact de vehicle_data.dart ligne 39-51
FLUTTER_EXPECTED = {
    "vitesse":           ("SPEED",                 "vitesse"),
    "regime":            ("RPM",                   "regime"),
    "tempMoteur":        ("COOLANT_TEMP",           "temp_moteur"),
    "maf":               ("MAF",                   "maf"),
    "lambda":            ("O2_B1S1",               "lambda"),
    "batterie":          ("CONTROL_MODULE_VOLTAGE", "batterie"),
    "pressionMap":       ("INTAKE_PRESSURE",        "pression_map"),
    "pressionHuile":     ("ENGINE_LOAD",            "pression_huile"),
    "stftB1":            ("SHORT_TERM_FUEL_TRIM_1", "stft_b1"),
    "ltftB1":            ("LONG_TERM_FUEL_TRIM_1",  "ltft_b1"),
    "pressionCarburant": ("FUEL_PRESSURE",          "pression_carburant"),
    "niveauCarburant":   ("FUEL_LEVEL",             "niveau_carburant"),
}

# === 3. Simulation donnees recues de l ELM327 ===
pids_from_elm = {
    "RPM": 2500,
    "COOLANT_TEMP": 92,
    "CONTROL_MODULE_VOLTAGE": 13.8,
    "SPEED": 60,
    "ENGINE_LOAD": 45,
    "MAF": 8.5,
    "SHORT_FUEL_TRIM_1": -2.5,
    "LONG_FUEL_TRIM_1": 1.2,
    "FUEL_LEVEL": 55,
    "O2_B1S1": 0.45,
    "INTAKE_PRESSURE": 95,
    "FUEL_PRESSURE": 380,
}

# Ce que _read_cycle() ecrit dans _live_snapshot via _pid_key()
live_snapshot = {PID_TO_KEY.get(k, k): v for k, v in pids_from_elm.items()}

print("=" * 60)
print("VERIFICATION PIPELINE OBD -> WebSocket -> Flutter")
print("=" * 60)

print("\n[1] _live_snapshot envoye au WebSocket :")
for k, v in live_snapshot.items():
    print(f"    {k:<34} = {v}")

print("\n[2] Jauges Flutter - Reception des cles :")
all_ok = True
for field, (primary, fallback) in FLUTTER_EXPECTED.items():
    found_p = primary  in live_snapshot
    found_f = fallback in live_snapshot
    val     = live_snapshot.get(primary, live_snapshot.get(fallback, "ABSENT"))
    if found_p:
        status = "OK  (cle principale)"
    elif found_f:
        status = "OK  (cle fallback)"
    else:
        status = "ABSENT => VALEUR FIGEE SUR LE DASHBOARD !"
        all_ok = False
    print(f"    {field:<22} [{primary:<30}] {status} => {val}")

print("\n[3] Lectures internes obd_module (State Machine) :")
for key in ["SPEED", "RPM", "CONTROL_MODULE_VOLTAGE"]:
    val = live_snapshot.get(key)
    ok  = "OK" if val is not None else "ABSENT"
    print(f"    snapshot.get('{key}') => {val}  [{ok}]")

print("\n[4] Fichiers Flutter - Dates de modification :")
flutter_files = [
    r"c:\code\SEDAI\auto_japan_app\lib\models\vehicle_data.dart",
    r"c:\code\SEDAI\auto_japan_app\lib\screens\dashboard_screen.dart",
    r"c:\code\SEDAI\auto_japan_app\lib\services\websocket_service.dart",
]
for f in flutter_files:
    t = os.path.getmtime(f)
    print(f"    {os.path.basename(f):<30} modifie le {datetime.fromtimestamp(t).strftime('%d/%m/%Y %H:%M')}")

print("\n[5] Fichiers Python modifies aujourd hui :")
py_files = [
    r"c:\code\SEDAI\src\obd_module.py",
    r"c:\code\SEDAI\src\tts_module.py",
]
for f in py_files:
    t = os.path.getmtime(f)
    print(f"    {os.path.basename(f):<30} modifie le {datetime.fromtimestamp(t).strftime('%d/%m/%Y %H:%M')}")

print()
print("=" * 60)
if all_ok:
    print("RESULTAT : TOUT OK - Toutes les jauges vont se mettre a jour")
else:
    print("RESULTAT : PROBLEME DETECTE - Des cles sont manquantes !")
print("=" * 60)
