#!/usr/bin/env python3
"""
Test OBD avancé - SEDAI debug v3
Corrige le bug d'écho décalé et reset l'ELM327 entre chaque protocole.
Compatible clones ELM327 v1.5 instables.
"""
import serial
import time

PORT    = "/dev/ttyUSB0"
BAUD    = 38400
TIMEOUT = 5

# ──────────────────────────────────────────────────────────────────────────────
def flush_and_send(ser, cmd, wait=1.5, label=None):
    """
    Vide le buffer, envoie la commande, attend `wait` secondes,
    puis lit TOUT ce qui est disponible.
    Retourne la réponse brute nettoyée.
    """
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    ser.write((cmd + "\r").encode())
    time.sleep(wait)

    raw  = b""
    deadline = time.time() + wait
    while time.time() < deadline:
        n = ser.inWaiting()
        if n:
            raw += ser.read(n)
            # Attendre un peu plus si la réponse arrive par morceaux
            time.sleep(0.05)
        else:
            if raw:
                break
            time.sleep(0.05)

    resp = raw.decode("ascii", errors="ignore").strip()
    # Retire les retours chariot / sauts de ligne internes pour l'affichage
    resp_display = " | ".join(line.strip() for line in resp.splitlines() if line.strip())
    tag = label or cmd
    print(f"  > {tag:22s} -> {resp_display}")
    return resp


def elm_reset(ser):
    """Reset complet de l'ELM327 et désactivation de l'écho (avec vérification)."""
    # 1. Reset matériel
    flush_and_send(ser, "ATZ", wait=2.5, label="ATZ (reset)")

    # 2. Désactivation écho — tentative 1
    r = flush_and_send(ser, "ATE0", wait=1.0, label="ATE0 (echo off)")
    if "OK" not in r and "ATE0" in r:
        # L'écho était encore actif, on renvoie
        r = flush_and_send(ser, "ATE0", wait=1.0, label="ATE0 retry")

    # 3. Headers off, espaces off — simplifie le parsing
    flush_and_send(ser, "ATH0",  wait=0.5, label="ATH0 (headers off)")
    flush_and_send(ser, "ATS0",  wait=0.5, label="ATS0 (spaces off)")
    flush_and_send(ser, "ATL0",  wait=0.5, label="ATL0 (linefeed off)")


# ──────────────────────────────────────────────────────────────────────────────
print(f"=== Test direct série sur {PORT} @ {BAUD} ===\n")

try:
    ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    time.sleep(0.5)

    # ── [1/4] Identification ────────────────────────────────────────────────
    print("[1/4] Identification ELM327")
    elm_reset(ser)
    flush_and_send(ser, "ATI",  wait=0.8, label="ATI  (version)")
    flush_and_send(ser, "AT@1", wait=0.8, label="AT@1 (description)")
    rv = flush_and_send(ser, "ATRV", wait=0.8, label="ATRV (tension)")
    print()

    # ── [2/4] Scan protocoles ───────────────────────────────────────────────
    print("[2/4] Scan des protocoles OBD-II")
    print("  ⚠  Le véhicule DOIT être sur contact MAR/ACC\n")

    protocols = {
        "1": "SAE J1850 PWM",
        "2": "SAE J1850 VPW",
        "3": "ISO 9141-2",
        "4": "ISO 14230-4 KWP (init 5 baud)",
        "5": "ISO 14230-4 KWP (init rapide)",
        "6": "ISO 15765-4 CAN 11bit/500k",
        "7": "ISO 15765-4 CAN 29bit/500k",
        "8": "ISO 15765-4 CAN 11bit/250k",
        "9": "ISO 15765-4 CAN 29bit/250k",
    }

    working_proto = None

    for num, name in protocols.items():
        print(f"  --- Protocole {num} : {name} ---")

        # Reset ELM327 avant chaque essai — indispensable pour les clones
        elm_reset(ser)

        # Sélection du protocole
        flush_and_send(ser, f"ATSP{num}", wait=0.8, label=f"ATSP{num}")

        # Délai prolongé pour les protocoles CAN (num >= 6)
        wait_pid = 5.0 if int(num) >= 6 else 4.0
        resp = flush_and_send(ser, "0100", wait=wait_pid, label="0100 (PIDs dispo)")

        if "41 00" in resp:
            print(f"\n  >>> PROTOCOLE {num} FONCTIONNE : {name} <<<\n")
            working_proto = num
            break
        elif "NO DATA" in resp:
            print(f"  (Pas de données — protocole absent ou véhicule hors contact)\n")
        elif "UNABLE TO CONNECT" in resp:
            print(f"  (Impossible de connecter — protocole rejeté par le véhicule)\n")
        elif "BUS INIT" in resp:
            print(f"  (BUS INIT détecté — protocole K-Line possible mais pas de réponse)\n")
        else:
            print(f"  (Réponse inattendue — continuer)\n")

    # ── [3/4] Résultat ─────────────────────────────────────────────────────
    if working_proto:
        print(f"[3/4] Protocole détecté : {protocols[working_proto]}")
        print(f"      → Mettre OBD_PROTOCOL = {working_proto!r} dans config.py\n")

        print("[4/4] Lecture PIDs de base")
        flush_and_send(ser, "010C", wait=2.0, label="010C (RPM)")
        flush_and_send(ser, "0105", wait=2.0, label="0105 (Temp moteur)")
        flush_and_send(ser, "010D", wait=2.0, label="010D (Vitesse)")
    else:
        print("[3/4] Aucun protocole spécifique ne répond.")
        print("      → Tentative AUTO (ATSP0)...\n")

        elm_reset(ser)
        flush_and_send(ser, "ATSP0", wait=1.0, label="ATSP0 (auto)")
        resp = flush_and_send(ser, "0100", wait=12.0, label="0100 (auto-detect)")

        if "41 00" in resp:
            print("\n  >>> AUTO-DÉTECTION RÉUSSIE <<<")
            # Lire le protocole utilisé
            p = flush_and_send(ser, "ATDPN", wait=1.0, label="ATDPN (proto actif)")
            print(f"      → Protocole détecté automatiquement : {p.strip()}")
            print(f"      → Mettre OBD_PROTOCOL = None dans config.py (auto)")
        else:
            print(f"\n  Auto-détection échouée : {resp}")
            print()
            print("  ┌─────────────────────────────────────────────────────┐")
            print("  │  DIAGNOSTIC : AUCUN PROTOCOLE NE RÉPOND             │")
            print("  ├─────────────────────────────────────────────────────┤")
            print("  │  Causes les plus probables (par ordre) :            │")
            print("  │  1. Contact véhicule PAS sur MAR/ACC                │")
            print("  │  2. ELM327 clone trop simplifié (firmware limité)   │")
            print("  │  3. Câble OBD-II mal branché / pin 16 sans masse    │")
            print("  │  4. Véhicule antérieur à 2001 (OBD-II partiel)     │")
            print("  └─────────────────────────────────────────────────────┘")

    ser.close()
    print("\n=== Fin du test ===")

except serial.SerialException as e:
    print(f"\nERREUR PORT SÉRIE : {e}")
    print("→ Vérifier : ls /dev/ttyUSB* (port correct ?)")
    print("→ Vérifier : sudo usermod -aG dialout sedai (permissions ?)")
except Exception as e:
    print(f"\nERREUR : {e}")
    import traceback; traceback.print_exc()
