import sys
import logging

# Configurer les logs pour tout voir
logging.basicConfig(level=logging.DEBUG)

# Ajouter 'src' au path pour importer les modules de SEDAI
sys.path.insert(0, 'src')

import obd
from obd.protocols.protocol_legacy import LegacyProtocol

# Vérifier que le monkeypatch de obd_module est actif si on l'importe
import obd_module

print("\n=== VERIFICATION MONKEYPATCH ===")
print("LegacyProtocol.parse_frame est patché :", LegacyProtocol.parse_frame.__name__ == "_patched_parse_frame")

# Connexion manuelle avec les mêmes paramètres que SEDAI
print("\n=== TENTATIVE DE CONNEXION ===")
c = obd.OBD('/dev/ttyUSB0', baudrate=38400, protocol='5', fast=False, check_voltage=False)

if not c.is_connected():
    print("Échec de connexion OBD !")
    sys.exit(1)

print("Connexion réussie ! Protocole actif :", c.protocol_name())
print("PIDs supportés détectés :", c.supported_commands)

print("\n=== REQUÊTE RPM ===")
r = c.query(obd.commands.RPM, force=True)
print("Response RPM :", r)
print("Response RPM Value :", r.value)
if r.messages:
    for i, m in enumerate(r.messages):
        print(f"Message {i} - data :", list(m.data))
        print(f"Message {i} - ecu :", m.ecu)
        print(f"Message {i} - parsed :", m.parsed())
else:
    print("Aucun message reçu pour RPM !")

print("\n=== REQUÊTE DTC (CODES DÉFAUTS) ===")
r_dtc = c.query(obd.commands.GET_DTC, force=True)
print("Response DTC :", r_dtc)
print("Response DTC Value :", r_dtc.value)
if r_dtc.messages:
    for i, m in enumerate(r_dtc.messages):
        print(f"Message DTC {i} - data :", list(m.data))
        print(f"Message DTC {i} - raw :", m.raw())
        print(f"Message DTC {i} - ecu :", m.ecu)
        print(f"Message DTC {i} - parsed :", m.parsed())
else:
    print("Aucun message reçu pour les DTCs !")

