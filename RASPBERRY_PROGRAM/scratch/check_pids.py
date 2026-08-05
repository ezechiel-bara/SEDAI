import obd
import logging

# Désactiver les logs pour avoir une sortie propre
logging.basicConfig(level=logging.CRITICAL)

print("--- LISTE DES COMMANDES VALIDES (PYTHON-OBD) ---")
# Lister les noms des attributs dans obd.commands qui sont de type OBDCommand
valid_cmds = []
for attr in dir(obd.commands):
    cmd = getattr(obd.commands, attr)
    if isinstance(cmd, obd.OBDCommand):
        valid_cmds.append(attr)

valid_cmds.sort()
for name in valid_cmds:
    print(name)

print("\n--- VÉRIFICATION DE VOS PIDS ACTUELS ---")
mes_pids = [
    "RPM", "COOLANT_TEMP", "CONTROL_MODULE_VOLTAGE",
    "SPEED", "ENGINE_LOAD", "MAF", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1",
    "THROTTLE_POS", "INTAKE_TEMP", "FUEL_LEVEL", "O2_B1S1",
    "INTAKE_PRESSURE", "FUEL_PRESSURE", "TIMING_ADVANCE", "OIL_TEMP"
]

for pid in mes_pids:
    if pid in valid_cmds:
        print(f"[OK] {pid}")
    else:
        print(f"[ERREUR] {pid} n'est pas reconnu par python-obd !")
