"""
obd_module.py — Acquisition des données OBD-II (SEDAI v2.1 — Safe Edition)

Changements v2.1 vs v2.0 :
  - Système de time-slicing par cycles (critique / standard / secondaire / optionnel)
  - Délai inter-PID (OBD_INTER_PID_DELAY) appliqué systématiquement
  - Compteur d'erreurs par PID : déconnexion uniquement après N erreurs globales
  - Reconnexion avec backoff exponentiel plafonné
  - Watchdog ELM327 pour détecter les freezes silencieux
  - clear_dtc() protégé : interdit si vitesse > 0 ou RPM actif
  - TRANS_TEMP et PIDs optionnels relégués en cycle lent (toutes les 30 itérations)
  - Intégration obd_safety et obd_normalizer

Comportement "read-only safe" garanti :
  - Uniquement commandes Mode 01 (lecture de données temps réel)
  - Mode 03 pour lecture DTC (passif)
  - Mode 04 (clear_dtc) uniquement sur commande explicite, véhicule arrêté
  - Aucune commande AT custom, aucun mode étendu
"""

import logging
import time
import threading
import queue
from typing import Any, Dict, List, Optional

import obd
from obd.protocols.protocol_legacy import LegacyProtocol

# Monkeypatch LegacyProtocol pour supporter les clones ELM327 buggés (sans headers sur KWP)
def _patched_parse_frame(self, frame):
    raw = frame.raw
    if len(raw) & 1:
        return False
    try:
        from binascii import unhexlify
        raw_bytes = bytearray(unhexlify(raw))
    except Exception:
        return False
        
    is_raw = False
    if len(raw_bytes) > 0:
        first_byte = raw_bytes[0]
        # Si le premier octet correspond à une réponse de Mode OBD standard (Mode + 0x40)
        # ex: 0x41 (Mode 01), 0x42 (Mode 02), 0x43 (Mode 03), 0x44, 0x49 (Mode 09)
        if first_byte in [0x41, 0x42, 0x43, 0x44, 0x49]:
            is_raw = True
            
    if is_raw:
        if len(raw_bytes) > 11:
            return False
        frame.data = raw_bytes
        frame.priority = 0
        frame.rx_id = 0
        frame.tx_id = 0
        return True
        
    # Comportement standard de python-obd si les en-têtes sont présents (et que ce n'est pas une trame brute)
    if len(raw_bytes) < 6:
        return False
    if len(raw_bytes) > 11:
        return False
        
    frame.data = raw_bytes[3:-1]
    frame.priority = raw_bytes[0]
    frame.rx_id = raw_bytes[1]
    frame.tx_id = raw_bytes[2]
    return True

LegacyProtocol.parse_frame = _patched_parse_frame


from config import (
    OBD_PORT, OBD_BAUDRATE, OBD_TIMEOUT,
    OBD_PROTOCOL, OBD_CHECK_VOLTAGE,
    OBD_BACKOFF_BASE, OBD_BACKOFF_FACTOR, OBD_BACKOFF_MAX,
    OBD_CYCLE_CRITICAL_INTERVAL,
    OBD_CYCLE_STANDARD_EVERY,
    OBD_CYCLE_SECONDARY_EVERY,
    OBD_CYCLE_OPTIONAL_EVERY,
    OBD_GLOBAL_ERROR_THRESHOLD, OBD_FALLBACK_PORTS,
    OBD_PIDS_CRITIQUES, OBD_PIDS_STANDARD,
    OBD_PIDS_SECONDAIRES, OBD_PIDS_OPTIONNELS,
    SEUIL_TEMP_TRANSMISSION_MAX,
    OBD_STABILIZATION_DELAY, OBD_IDLE_RPM_THRESHOLD,
    OBD_DEGRADED_MODE_INTERVAL, DEGRADED_VOLTAGE_THRESHOLD,
    DEGRADED_VOLTAGE_RECOVERY_THRESHOLD, DEGRADED_RECOVERY_CYCLES,
    OBD_CAN_BUDGET_MS, LOG_LEVEL
)
from obd_safety import RateLimiter, PIDHealthTracker, ELM327Watchdog, BackoffCalculator
from obd_normalizer import OBDNormalizer

logger = logging.getLogger("OBD")

# Commande personnalisée pour les DTCs permanents (Mode 0A)
# python-obd ne la fournit pas par défaut, mais elle utilise le même décodeur standard 'dtc'
try:
    GET_PERMANENT_DTC = obd.OBDCommand(
        "GET_PERMANENT_DTC",
        "Get permanent DTCs",
        b"0A",
        0,
        obd.decoders.dtc,
        ecu=obd.commands.GET_DTC.ecu if hasattr(obd.commands, "GET_DTC") else 255,
        fast=False,
        header=obd.commands.GET_DTC.header if hasattr(obd.commands, "GET_DTC") else b'7E0'
    )
except Exception as e:
    logger.error(f"[OBD] Impossible de créer la commande personnalisée Mode 0A : {e}")
    GET_PERMANENT_DTC = None


# Synchroniser les logs internes de python-obd avec le LOG_LEVEL global
# (Utilise CRITICAL si non spécifié pour éviter le bruit des clones ELM)
obd_log_level = getattr(logging, LOG_LEVEL, logging.CRITICAL)
obd.logger.setLevel(obd_log_level)

# Délai de stabilisation après connexion physique.
# Laisse l'ELM327 terminer son handshake CAN avant le premier PID.
_ELM_INIT_DELAY_S: float = 3.0


# ══════════════════════════════════════════════════════════════════════════════
# Cycle descriptor
# ══════════════════════════════════════════════════════════════════════════════

# Chaque cycle associe un nom de groupe PID à son intervalle (en nombre
# d'itérations critiques). Le cycle critique tourne à chaque itération.
_CYCLES = [
    ("critique",   OBD_PIDS_CRITIQUES,   1),
    ("standard",   OBD_PIDS_STANDARD,    OBD_CYCLE_STANDARD_EVERY),
    ("secondaire", OBD_PIDS_SECONDAIRES, OBD_CYCLE_SECONDARY_EVERY),
    ("optionnel",  OBD_PIDS_OPTIONNELS,  OBD_CYCLE_OPTIONAL_EVERY),
]


def _resolve_command(pid_name: str) -> Optional[obd.OBDCommand]:
    """
    Résout un nom de PID (str) en commande python-obd.

    Retourne None si le PID est inconnu, sans lever d'exception.
    Cela évite tout crash si un nom est mal orthographié en config.
    """
    try:
        # La méthode recommandée par python-obd pour récupérer par nom
        return obd.commands[pid_name]
    except KeyError:
        logger.warning(f"[OBD] PID inconnu dans la config : '{pid_name}' — ignoré.")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# OBDModule
# ══════════════════════════════════════════════════════════════════════════════

class OBDModule(threading.Thread):
    """
    Thread d'acquisition OBD-II avec time-slicing, rate limiting et watchdog.

    Architecture interne :
      1. RateLimiter      → délai inter-PID (150 ms)
      2. PIDHealthTracker → désactive les PIDs systématiquement en erreur
      3. ELM327Watchdog   → détecte les freezes silencieux de l'adaptateur
      4. BackoffCalculator→ reconnexion progressive
      5. OBDNormalizer    → sortie JSON IA-ready
    """

    def __init__(
        self,
        shared_state: Dict[str, Any],
        state_lock: threading.Lock,
        action_queue: queue.Queue,
        event_stop: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.state_lock   = state_lock
        self.action_queue = action_queue
        self.event_stop   = event_stop

        # Connexion OBD
        self.connection: Optional[obd.OBD] = None
        self.connected: bool = False

        # Couche sécurité
        self._rate_limiter  = RateLimiter()
        self._pid_tracker   = PIDHealthTracker()
        self._watchdog      = ELM327Watchdog()
        self._backoff       = BackoffCalculator(
            base_s=OBD_BACKOFF_BASE,
            factor=OBD_BACKOFF_FACTOR,
            max_s=OBD_BACKOFF_MAX,
        )

        # Normalisation
        self._normalizer: Optional[OBDNormalizer] = None

        # Compteur d'itérations critiques (référence pour le time-slicing)
        self._iteration: int = 0

        # Compteur d'erreurs globales consécutives (toute requête PID)
        self._global_errors: int = 0

        # Snapshot courant des données (toutes catégories cumulées)
        self._live_snapshot: Dict[str, Any] = {}

        # Suivi de la stabilité moteur pour Mode 04 safety
        self._last_unstable_time: float = 0.0

        # State Machine et Mode dégradé
        self.vehicle_state: str = "STARTING"
        self.is_degraded_mode: bool = False
        self._degraded_recovery_counter: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Connexion
    # ──────────────────────────────────────────────────────────────────────────

    def _try_connect_port(self, port: Optional[str]) -> Optional[obd.OBD]:
        """
        Tente une connexion OBD sur un port spécifique avec détection de protocole intelligente.
        Retourne l'objet OBD si connecté, None sinon.
        Si `port` est None, utilise l'auto-scan natif de python-OBD.

        IMPORTANT (v2.3) :
          Les clones ELM327 échouent souvent à détecter automatiquement le protocole
          du véhicule (KWP, CAN, etc.). Si `OBD_PROTOCOL` est réglé sur `"auto"`,
          nous testons les protocoles les plus fréquents en séquence pour garantir
          la connexion sur n'importe quel véhicule.
        """
        protocols_to_try = [OBD_PROTOCOL]
        if OBD_PROTOCOL == "auto" or OBD_PROTOCOL is None:
            # Essayer d'abord la recherche auto de l'ELM, puis forcer les plus courants :
            # CAN (6), KWP Fast (5 - votre véhicule), ISO9141 (3), KWP Slow (4)
            protocols_to_try = [None, "6", "5", "3", "4", "7", "8", "9"]

        for proto in protocols_to_try:
            try:
                proto_label = proto if proto else "Auto-détection"
                label = port if port else "auto-scan"
                logger.info(f"[OBD] Essai de connexion sur {label} avec protocole : {proto_label}")

                if port is not None:
                    conn = obd.OBD(
                        port,
                        baudrate=OBD_BAUDRATE,
                        protocol=proto,
                        fast=False,
                        timeout=OBD_TIMEOUT,
                        check_voltage=OBD_CHECK_VOLTAGE,
                    )
                else:
                    conn = obd.OBD(
                        fast=False,
                        timeout=OBD_TIMEOUT,
                        protocol=proto,
                        check_voltage=OBD_CHECK_VOLTAGE,
                    )

                # Si on est connecté à l'ECU du véhicule, c'est parfait !
                if conn.status() in [obd.OBDStatus.CAR_CONNECTED, obd.OBDStatus.OBD_CONNECTED]:
                    logger.info(
                        f"[OBD] Véhicule connecté sur {label} ! "
                        f"Protocole retenu : {conn.protocol_name()} (statut : {conn.status()})"
                    )
                    return conn

                # Si l'ELM est détecté sur le port mais le contact véhicule est coupé (ELM_CONNECTED),
                # on accepte la connexion pour démarrer l'app, mais on ne peut pas tester les autres protocoles.
                if conn.status() == obd.OBDStatus.ELM_CONNECTED:
                    logger.info(
                        f"[OBD] Adaptateur ELM327 détecté sur {label}, mais véhicule hors contact "
                        f"(statut : {conn.status()})"
                    )
                    return conn

                # Si l'adaptateur ELM327 lui-même ne répond pas (NOT_CONNECTED), inutile de tester d'autres protocoles OBD
                if conn.status() == obd.OBDStatus.NOT_CONNECTED:
                    logger.debug(f"[OBD] L'adaptateur ELM327 n'a pas répondu sur {label} (pas de communication série).")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    break

                # Fermeture propre avant essai du protocole suivant
                try:
                    conn.close()
                except Exception:
                    pass

            except Exception as e:
                label = port if port else "auto-scan"
                logger.debug(f"[OBD] Port {label} (protocole {proto}) inaccessible : {e}")

        return None

    def connect(self) -> bool:
        """
        Tente d'établir la connexion OBD-II.

        Stratégie multi-ports (v2.2) :
          1. Port configuré en priorité (OBD_PORT)
          2. Ports fallback en séquence (OBD_FALLBACK_PORTS)
          3. Auto-scan python-OBD en dernier recours
          4. Délai de stabilisation ELM _ELM_INIT_DELAY_S avant la 1ère requête
          5. Vérification de tension (commande légère, sans risque)

        Returns:
            True si connecté et opérationnel.
        """
        import os
        import serial
        import sys

        # --- Éviter le scan inutile si aucun port série USB n'est présent sous Linux ---
        if sys.platform.startswith("linux"):
            import glob
            system_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
            if not system_ports:
                logger.info(
                    "[OBD] Aucun port série USB physique (/dev/ttyUSB* ou /dev/ttyACM*) détecté. "
                    "Recherche suspendue. Veuillez brancher l'adaptateur ELM327."
                )
                with self.state_lock:
                    self.shared_state["statut_obd"] = "déconnecté"
                self.connected = False
                return False

        # Construire la séquence complète des ports à tenter
        ports_to_try: List[Optional[str]] = [OBD_PORT] + OBD_FALLBACK_PORTS + [None]

        conn: Optional[obd.OBD] = None
        port_actuel: Optional[str] = None
        elm_physique_port = None

        for port in ports_to_try:
            if port is not None:
                # Si le port n'existe pas physiquement dans le système, on l'ignore silencieusement
                if not os.path.exists(port):
                    logger.debug(f"[OBD] Le port configuré {port} n'existe pas physiquement. Ignoré.")
                    continue

                label = port
                logger.info(
                    f"[OBD] Tentative de connexion sur {label} "
                    f"(baudrate={OBD_BAUDRATE}, fast=False, timeout={OBD_TIMEOUT}s)..."
                )

                # --- Pré-détection matérielle ---
                try:
                    with serial.Serial(port, OBD_BAUDRATE, timeout=0.8) as s:
                        # Si le port s'ouvre, on vérifie s'il répond aux commandes AT basiques
                        s.write(b"ATZ\r")
                        time.sleep(0.3)
                        s.reset_input_buffer()
                        s.write(b"ATI\r")
                        time.sleep(0.1)
                        resp = s.read(50)
                        if b"ELM" in resp or b"OBD" in resp or b"OK" in resp:
                            elm_physique_port = port
                            logger.info(f"[OBD] Présence matérielle de l'ELM327 confirmée sur {port}.")
                except serial.SerialException as se:
                    logger.error(
                        f"[OBD] Impossible d'ouvrir le port {port} (port occupé ou permissions insuffisantes) : {se}"
                    )
                    continue  # Inutile de lancer obd.OBD, passons au port suivant
                except Exception as e:
                    logger.debug(f"[OBD] Échec mineur de pré-détection sur {port} : {e}")
            else:
                label = "auto-scan"
                logger.info(
                    f"[OBD] Tentative de connexion sur {label} "
                    f"(fast=False, timeout={OBD_TIMEOUT}s)..."
                )

            conn = self._try_connect_port(port)
            if conn is not None:
                port_actuel = conn.port_name()
                break
                
            # Si on a détecté l'ELM physiquement mais python-obd refuse la connexion
            if elm_physique_port is not None:
                logger.warning(
                    f"[OBD] ELM327 détecté sur {port}, mais la connexion OBD a échoué. "
                    "Le véhicule est probablement hors contact ou l'adaptateur n'est pas branché à la prise OBD."
                )
                with self.state_lock:
                    self.shared_state["statut_obd"] = "ELM présent, en attente véhicule"
                self.connected = False
                return False

        if conn is None or conn.status() == obd.OBDStatus.NOT_CONNECTED:
            self.connected = False
            logger.error(
                "[OBD] Aucune interface ELM327 détectée. "
                "Vérifiez que le câble USB est bien branché au Raspberry Pi."
            )
            with self.state_lock:
                self.shared_state["statut_obd"] = "déconnecté"
            return False

        self.connection = conn
        conn_status = conn.status()

        # Libellé humain du statut de connexion
        _STATUS_LABEL = {
            obd.OBDStatus.ELM_CONNECTED: "ELM327 détecté — véhicule hors contact (MAR/ACC requis)",
            obd.OBDStatus.OBD_CONNECTED: "Protocole OBD détecté — ECU silencieux",
            obd.OBDStatus.CAR_CONNECTED: "Véhicule connecté — ECU actif",
        }
        logger.info(
            f"[OBD] Interface sur {port_actuel} : "
            f"{_STATUS_LABEL.get(conn_status, conn_status)}. "
            f"Stabilisation {_ELM_INIT_DELAY_S}s..."
        )

        # Délai de stabilisation : l'ELM327 finalise son handshake CAN
        time.sleep(_ELM_INIT_DELAY_S)

        # Vérification de tension (commande AT RV — sans impact ECU)
        tension = self._check_voltage()
        if tension is not None:
            logger.info(f"[OBD] Tension batterie : {tension:.1f} V")
            if tension < 11.5:
                logger.warning(
                    "[OBD] Tension faible (< 11.5 V) — "
                    "les lectures peuvent être instables."
                )
        else:
            logger.info("[OBD] Tension non disponible sur cet adaptateur (normal sur clone v1.5).")

        # Log du protocole et des PIDs supportés (seulement si ECU actif)
        if conn_status == obd.OBDStatus.CAR_CONNECTED:
            try:
                proto_id   = self.connection.protocol_id()
                proto_name = self.connection.protocol_name()
                logger.info(f"[OBD] Protocole détecté : {proto_id} ({proto_name})")
                supported = [str(cmd) for cmd in self.connection.supported_commands
                             if hasattr(cmd, 'mode') and cmd.mode == 1]
                logger.info(f"[OBD] PIDs Mode 01 supportés par l'ECU : {len(supported)} commandes.")
            except Exception:
                pass

        # Réinitialisation des compteurs après connexion réussie
        self._pid_tracker.reset()
        self._normalizer = OBDNormalizer(
            self.shared_state.get("vehicle_info", {})
        )
        self._normalizer.reset_history()
        self._iteration = 0
        self._global_errors = 0
        self._live_snapshot.clear()

        self._watchdog.start()
        self._backoff.reset()

        self.connected = True

        # Statut OBD selon le niveau de connexion réel
        statut_label = {
            obd.OBDStatus.ELM_CONNECTED: "en attente contact",
            obd.OBDStatus.OBD_CONNECTED: "protocole détecté",
            obd.OBDStatus.CAR_CONNECTED: "connecté",
        }.get(conn_status, "connecté (partiel)")

        with self.state_lock:
            self.shared_state["statut_obd"] = statut_label
            self.shared_state.pop("obd_reconnect_info", None)

        logger.info(f"[OBD] Connexion établie sur {port_actuel} — statut : {statut_label}.")
        return True

    def _check_voltage(self) -> Optional[float]:
        """
        Lit la tension via AT RV (commande AT sans interaction ECU).
        C'est la commande la moins intrusive possible sur l'ELM327.
        """
        if self.connection is None:
            return None
        try:
            response = self.connection.query(obd.commands.ELM_VOLTAGE)
            if not response.is_null():
                val = response.value
                return float(val.magnitude) if hasattr(val, "magnitude") else float(val)
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Requête PID sécurisée
    # ──────────────────────────────────────────────────────────────────────────

    def _query_pid_safe(self, command: obd.OBDCommand, pid_name: str) -> Optional[Any]:
        """
        Interroge un PID avec protection rate limiter + health tracker.

        Différence v2.1 vs v2.0 :
          - Ne déconnecte PAS immédiatement sur une erreur isolée
          - Incrémente le compteur global d'erreurs consécutives
          - La déconnexion est déclenchée uniquement si ce compteur dépasse
            OBD_GLOBAL_ERROR_THRESHOLD (erreur systémique, pas PID spécifique)

        Args:
            command  : commande python-obd à envoyer
            pid_name : nom string du PID (pour le tracker)

        Returns:
            Valeur numérique propre, ou None si réponse nulle/erreur.
        """
        if not self.connected or self.connection is None:
            return None

        # Vérification health tracker : PID en quarantaine ?
        if not self._pid_tracker.is_active(pid_name):
            return None

        # Respecter le délai inter-PID (rate limiter)
        self._rate_limiter.wait()

        try:
            # force=True est OBLIGATOIRE avec les clones KWP qui renvoient
            # une liste de PIDs supportés tronquée ou vide.
            response = self.connection.query(command, force=True)
            self._rate_limiter.record()

            if response.is_null():
                # Réponse vide = PID non supporté par l'ECU (NO DATA)
                # Ce n'est PAS une erreur de communication.
                self._pid_tracker.record_failure(pid_name)
                return None

            # Succès : réinitialiser les compteurs d'erreur
            self._pid_tracker.record_success(pid_name)
            self._watchdog.record_valid_response()
            self._global_errors = 0

            val = response.value
            return float(val.magnitude) if hasattr(val, "magnitude") else val

        except Exception as e:
            self._rate_limiter.record()
            self._pid_tracker.record_failure(pid_name)
            self._global_errors += 1

            logger.warning(
                f"[OBD] Erreur PID '{pid_name}' "
                f"({self._global_errors}/{OBD_GLOBAL_ERROR_THRESHOLD}) : {e}"
            )

            if self._global_errors >= OBD_GLOBAL_ERROR_THRESHOLD:
                logger.error(
                    f"[OBD] {self._global_errors} erreurs consécutives globales — "
                    "problème de communication avec l'ELM327. Reconnexion programmée."
                )
                self.connected = False

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Time-Slicing par cycles
    # ──────────────────────────────────────────────────────────────────────────

    def _read_cycle(self) -> str:
        """
        Exécute les PIDs du cycle courant selon le time-slicing.

        Logique :
          - À chaque itération, le cycle CRITIQUE est toujours exécuté.
          - Si en mode dégradé, ignore les autres cycles.
          - Les autres cycles sont exécutés seulement si `_iteration`
            est un multiple de leur intervalle.
          - Les résultats s'accumulent dans `_live_snapshot`.
        Returns:
            Nom du cycle le plus "avancé" exécuté dans cette itération.
        """
        active_cycle = "critique"
        cycle_start_time = time.time()

        for cycle_name, pid_list, every_n in _CYCLES:
            if self.is_degraded_mode and cycle_name != "critique":
                # En mode dégradé, on ne lit QUE le cycle critique (Max 3 PIDs)
                continue

            if self._iteration % every_n != 0:
                continue

            active_cycle = cycle_name
            for pid_name in pid_list:
                # [BUDGET LATENCE CAN] Ne jamais couper le critique, restreindre le reste
                if cycle_name != "critique":
                    if (time.time() - cycle_start_time) > (OBD_CAN_BUDGET_MS / 1000.0):
                        logger.warning(
                            f"[OBD] Budget latence CAN dépassé (> {OBD_CAN_BUDGET_MS}ms). "
                            "Fin anticipée du cycle."
                        )
                        return active_cycle

                cmd = _resolve_command(pid_name)
                if cmd is None:
                    continue

                key = self._pid_key(pid_name)
                value = self._query_pid_safe(cmd, pid_name)

                if value is not None:
                    self._live_snapshot[key] = (
                        round(value, 2) if isinstance(value, float) else value
                    )

                # Ne pas continuer si déconnexion détectée en cours de cycle
                if not self.connected:
                    return active_cycle

        return active_cycle

    @staticmethod
    def _pid_key(pid_name: str) -> str:
        """Convertit le nom de commande OBD en clé envoyée au WebSocket Flutter.

        IMPORTANT : Les clés doivent correspondre EXACTEMENT aux clés attendues
        par vehicle_data.dart (fromJson). Toute divergence = valeur figée sur le tableau de bord.
        """
        _PID_TO_KEY = {
            # ── Clés critiques (cycle ~1 Hz) ────────────────────────────────
            "RPM":                    "RPM",
            "COOLANT_TEMP":           "COOLANT_TEMP",
            "CONTROL_MODULE_VOLTAGE": "CONTROL_MODULE_VOLTAGE",   # ← batterie Flutter
            # ── Clés standard ───────────────────────────────────────────────
            "SPEED":                  "SPEED",
            "ENGINE_LOAD":            "ENGINE_LOAD",               # Charge moteur (%)
            "MAF":                    "MAF",
            "SHORT_FUEL_TRIM_1":      "SHORT_TERM_FUEL_TRIM_1",   # ← stft_b1 Flutter
            "LONG_FUEL_TRIM_1":       "LONG_TERM_FUEL_TRIM_1",    # ← ltft_b1 Flutter
            # ── Clés secondaires ────────────────────────────────────────────
            "THROTTLE_POS":           "THROTTLE_POS",
            "INTAKE_TEMP":            "INTAKE_TEMP",
            "FUEL_LEVEL":             "FUEL_LEVEL",                # ← niveau_carburant Flutter
            "O2_B1S1":                "O2_B1S1",                   # ← lambda Flutter
            # ── Clés optionnelles ────────────────────────────────────────────
            "INTAKE_PRESSURE":        "INTAKE_PRESSURE",           # ← pression_map Flutter
            "FUEL_PRESSURE":          "FUEL_PRESSURE",             # ← pression_carburant Flutter
            "TIMING_ADVANCE":         "TIMING_ADVANCE",
            "ENGINE_OIL_PRESSURE":    "OIL_PRESSURE",              # ← pression_huile Flutter
            "OIL_TEMP":               "temp_transmission",         # ← temp_transmission Flutter
        }
        # Si le PID n'est pas dans la table, retourner le nom original (sûr)
        return _PID_TO_KEY.get(pid_name, pid_name)


    # ──────────────────────────────────────────────────────────────────────────
    # DTC
    # ──────────────────────────────────────────────────────────────────────────

    def get_dtc(self) -> List[str]:
        """
        Récupère et catégorise l'ensemble des codes défauts (DTC) du véhicule.

        Interroge séquentiellement de manière sécurisée et indépendante :
          - Mode 03 : Confirmés (GET_DTC)
          - Mode 07 : En attente / Pending (GET_CURRENT_DTC)
          - Mode 0A : Permanents (GET_PERMANENT_DTC, si disponible)

        Met à jour les listes spécifiques dans le shared_state et renvoie
        une liste plate fusionnée et dédupliquée pour la rétrocompatibilité.

        Returns:
            Liste de tous les codes DTC uniques détectés (ex: ['P0104', 'P0300']).
        """
        confirmes = []
        en_attente = []
        permanents = []
        descriptions = {}

        if not self.connected or self.connection is None:
            return []

        # 1. Mode 03 : DTC Confirmés
        try:
            resp_confirmed = self.connection.query(obd.commands.GET_DTC)
            if not resp_confirmed.is_null() and isinstance(resp_confirmed.value, list):
                for code in resp_confirmed.value:
                    if code and len(code) >= 2:
                        confirmes.append(code[0])
                        descriptions[code[0]] = code[1]
                    elif code:
                        confirmes.append(code[0])
        except Exception as e:
            logger.warning(f"[OBD] Erreur lors de la lecture des DTCs confirmés (Mode 03) : {e}")

        # 2. Mode 07 : DTC En attente (Pending)
        try:
            resp_pending = self.connection.query(obd.commands.GET_CURRENT_DTC)
            if not resp_pending.is_null() and isinstance(resp_pending.value, list):
                for code in resp_pending.value:
                    if code and len(code) >= 2:
                        en_attente.append(code[0])
                        descriptions[code[0]] = code[1]
                    elif code:
                        en_attente.append(code[0])
        except Exception as e:
            logger.warning(f"[OBD] Erreur lors de la lecture des DTCs en attente (Mode 07) : {e}")

        # 3. Mode 0A : DTC Permanents (si supporté par le véhicule et l'ELM)
        if GET_PERMANENT_DTC is not None:
            try:
                resp_permanent = self.connection.query(GET_PERMANENT_DTC)
                if not resp_permanent.is_null() and isinstance(resp_permanent.value, list):
                    for code in resp_permanent.value:
                        if code and len(code) >= 2:
                            permanents.append(code[0])
                            descriptions[code[0]] = code[1]
                        elif code:
                            permanents.append(code[0])
            except Exception as e:
                logger.warning(f"[OBD] Erreur lors de la lecture des DTCs permanents (Mode 0A) : {e}")

        # Stockage atomique et sécurisé des sous-listes dans shared_state
        with self.state_lock:
            self.shared_state["dtcs_confirmes"] = confirmes
            self.shared_state["dtcs_en_attente"] = en_attente
            self.shared_state["dtcs_permanents"] = permanents
            self.shared_state["dtc_descriptions"] = descriptions

        # Rapport dans la console de logs
        total_found = len(confirmes) + len(en_attente) + len(permanents)
        if total_found > 0:
            logger.info(
                f"[OBD] Bilan DTCs — Confirmés : {confirmes if confirmes else 'Aucun'} | "
                f"En attente : {en_attente if en_attente else 'Aucun'} | "
                f"Permanents : {permanents if permanents else 'Aucun'}"
            )
        else:
            logger.info("[OBD] Bilan DTCs — Aucun code défaut détecté (véhicule sain).")

        # Fusion dédupliquée et triée pour rétrocompatibilité totale
        merged = list(set(confirmes + en_attente + permanents))
        return sorted(merged)

    def _update_engine_state(self) -> None:
        """
        Met à jour le chronomètre de stabilité moteur.
        Remet le timer à now() si le véhicule bouge ou n'est pas au ralenti.
        """
        vitesse = self._live_snapshot.get("SPEED", 0)
        regime  = self._live_snapshot.get("RPM", 0)

        is_moving  = isinstance(vitesse, (int, float)) and vitesse > 0
        is_high_rpm = isinstance(regime, (int, float)) and regime > OBD_IDLE_RPM_THRESHOLD

        if is_moving or is_high_rpm:
            self._last_unstable_time = time.time()

    def clear_dtc(self, confirmed: bool = False) -> bool:
        """
        Efface les codes défauts (Mode 04).

        SÉCURITÉ (v2.1) — CONDITIONS STRICTES :
          1. véhicule arrêté (vitesse == 0)
          2. moteur sous la barre de ralenti (RPM < OBD_IDLE_RPM_THRESHOLD)
          3. stabilisé depuis au moins OBD_STABILIZATION_DELAY secondes
          4. L'utilisateur doit explicitement confirmer l'action (confirmed=True)

        Returns:
            True si l'effacement a été envoyé et accepté, False sinon.
        """
        if not confirmed:
            logger.warning("[OBD] clear_dtc() REFUSÉ — confirmation explicite requise (confirmed=False).")
            return False

        if not self.connected or self.connection is None:
            return False

        # Garde de sécurité : vérifier le contexte véhicule
        vitesse = self._live_snapshot.get("SPEED", 0)
        regime  = self._live_snapshot.get("RPM", 0)

        if isinstance(vitesse, (int, float)) and vitesse > 0:
            logger.warning(
                "[OBD] clear_dtc() REFUSÉ — véhicule en mouvement "
                f"(vitesse={vitesse} km/h). Arrêtez le véhicule."
            )
            return False

        if isinstance(regime, (int, float)) and regime > OBD_IDLE_RPM_THRESHOLD:
            logger.warning(
                "[OBD] clear_dtc() REFUSÉ — régime moteur trop élevé "
                f"(régime={regime} RPM). Cette action nécessite l'arrêt ou le ralenti."
            )
            return False

        now = time.time()
        # Si on n'a jamais initialisé le chronomètre ou s'il n'est pas stable
        if self.vehicle_state != "STABLE":
            logger.warning(
                "[OBD] clear_dtc() REFUSÉ — Le véhicule n'est pas dans l'état STABLE "
                f"(état actuel : {self.vehicle_state})."
            )
            return False

        if (now - self._last_unstable_time) < OBD_STABILIZATION_DELAY:
            logger.warning(
                "[OBD] clear_dtc() REFUSÉ — véhicule instable récemment. "
                f"Attendez {OBD_STABILIZATION_DELAY}s après arrêt."
            )
            return False

        try:
            logger.warning(
                "[OBD] ATTENTION : Effacement des codes défauts (Mode 04) — "
                "remet à zéro les moniteurs ECU."
            )
            response = self.connection.query(obd.commands.CLEAR_DTC)
            success = not response.is_null()
            if success:
                logger.info("[OBD] DTC effacés avec succès.")
            return success
        except Exception as e:
            logger.error(f"[OBD] Erreur effacement DTC : {e}")
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # State Machine
    # ──────────────────────────────────────────────────────────────────────────

    def _update_vehicle_state_machine(self) -> None:
        """
        Gère la Vehicle Stability State Machine.
        Calcule l'état ECU global.
        États : STARTING -> CRITICAL -> DEGRADED -> TRANSIENT -> STABLE
        """
        tension = self._live_snapshot.get("CONTROL_MODULE_VOLTAGE")
        voltage_drop   = isinstance(tension, (int, float)) and tension < DEGRADED_VOLTAGE_THRESHOLD
        hardware_faults = self._global_errors > 0

        # Règle d'Entrée (Hystérésis Mode Dégradé)
        if voltage_drop or hardware_faults:
            self._degraded_recovery_counter = 0  # reset compteur de guérison
            if not self.is_degraded_mode:
                logger.warning(
                    "[OBD] ⚠️ PASSAGE EN MODE DÉGRADÉ "
                    f"(tension_basse={voltage_drop}, hw_faults={hardware_faults}) — Limite à 3 PIDs max."
                )
                self.is_degraded_mode = True
                self.action_queue.put({
                    "type": "speak",
                    "text": "Mode dégradé activé. Diagnostic limité."
                })
        else:
            # S'il y a un retour à la normale potentiel (Hystérésis)
            if self.is_degraded_mode:
                voltage_recovered = isinstance(tension, (int, float)) and tension > DEGRADED_VOLTAGE_RECOVERY_THRESHOLD
                if voltage_recovered and not hardware_faults:
                    self._degraded_recovery_counter += 1
                    if self._degraded_recovery_counter >= DEGRADED_RECOVERY_CYCLES:
                        logger.info("[OBD] Rétablissement au Mode Normal confirmé (Hystérésis atteinte).")
                        self.is_degraded_mode = False
                        self._degraded_recovery_counter = 0
                        self.action_queue.put({
                            "type": "speak",
                            "text": "Tension stabilisée. Mode dégradé levé."
                        })
                else:
                    self._degraded_recovery_counter = 0

        # Evaluation State Machine Véhicule Global
        if self._iteration < 5:
            self.vehicle_state = "STARTING"
            return

        if hardware_faults:
            self.vehicle_state = "CRITICAL"
            return

        if self.is_degraded_mode:
            self.vehicle_state = "DEGRADED"
            return

        vitesse = self._live_snapshot.get("SPEED", 0)
        regime  = self._live_snapshot.get("RPM", 0)

        is_moving  = isinstance(vitesse, (int, float)) and vitesse > 0
        is_high_rpm = isinstance(regime, (int, float)) and regime > OBD_IDLE_RPM_THRESHOLD

        if is_moving or is_high_rpm:
            self.vehicle_state = "TRANSIENT"
        else:
            now = time.time()
            if (now - self._last_unstable_time) >= OBD_STABILIZATION_DELAY:
                self.vehicle_state = "STABLE"
            else:
                self.vehicle_state = "TRANSIENT"

    @staticmethod
    def _translate_for_normalizer(obd_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traduit les clés OBD d'origine (ex: 'CONTROL_MODULE_VOLTAGE') vers les
        clés courtes attendues par OBDNormalizer._PID_SCHEMA (ex: 'tension').

        Le normalizer utilise son propre schéma interne — il ne doit pas être
        modifié car il sert aussi au diagnostic IA. Cette couche de traduction
        isole les deux contrats de nommage :
          - WebSocket Flutter : clés OBD originales (SPEED, RPM, ...)
          - Normalizer/IA     : clés courtes françaises (vitesse, regime, ...)
        """
        _OBD_TO_NORM = {
            "RPM":                    "regime",
            "COOLANT_TEMP":           "temp_moteur",
            "CONTROL_MODULE_VOLTAGE": "tension",
            "SPEED":                  "vitesse",
            "ENGINE_LOAD":            "charge",
            "MAF":                    "maf",
            "INTAKE_PRESSURE":        "map",
            "SHORT_TERM_FUEL_TRIM_1": "stft_b1",
            "LONG_TERM_FUEL_TRIM_1":  "ltft_b1",
            "THROTTLE_POS":           "papillon",
            "TIMING_ADVANCE":         "avance",
            "INTAKE_TEMP":            "temp_admission",
            "FUEL_LEVEL":             "carburant",
            "FUEL_PRESSURE":          "pression_carburant",
            "O2_B1S1":                "lambda",
            "OIL_PRESSURE":           "pression_huile",
            "temp_transmission":      "temp_transmission",
        }
        return {
            _OBD_TO_NORM.get(k, k): v
            for k, v in obd_snapshot.items()
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Boucle principale
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Boucle principale du thread d'acquisition OBD-II.

        Comportement :
          1. Si déconnecté → tentative de connexion avec backoff exponentiel
          2. Si connecté   → exécution du cycle de PIDs selon le time-slicing
          3. Vérification watchdog à chaque itération
          4. Mise à jour atomique du shared_state
          5. Attente OBD_CYCLE_CRITICAL_INTERVAL avant la prochaine itération

        Le thread continue à fonctionner même si un PID échoue :
        seul un échec systémique (N erreurs consécutives globales)
        ou un freeze watchdog déclenche une reconnexion.
        """
        logger.info("[OBD] Démarrage du thread d'acquisition (time-slicing v2.1).")

        while not self.event_stop.is_set():

            # ── Reconnexion ──────────────────────────────────────────────────
            if not self.connected:
                with self.state_lock:
                    self.shared_state["statut_obd"] = "déconnecté"

                delay = self._backoff.next_delay()
                attempt = self._backoff.attempt_count

                # Publier l'info de reconnexion pour le broadcast WebSocket
                with self.state_lock:
                    self.shared_state["obd_reconnect_info"] = {
                        "essai": attempt,
                        "prochaine_tentative_s": round(delay),
                        "ports_tentes": [OBD_PORT] + OBD_FALLBACK_PORTS,
                    }

                logger.info(
                    f"[OBD] Tentative de reconnexion dans {delay:.0f}s "
                    f"(essai #{attempt})..."
                )
                # Attente interruptible (respecte event_stop)
                if self.event_stop.wait(timeout=delay):
                    break

                if not self.connect():
                    continue

            # ── Watchdog ─────────────────────────────────────────────────────
            if self._watchdog.is_frozen():
                logger.warning(
                    "[OBD] Watchdog déclenché — ELM327 potentiellement gelé. "
                    "Forçage de la reconnexion."
                )
                self.connected = False
                if self.connection:
                    try:
                        self.connection.close()
                    except Exception:
                        pass
                    self.connection = None
                self._watchdog.stop()
                continue

            # ── State Machine Véhicule ───────────────────────────────────────
            self._update_vehicle_state_machine()

            # ── Cycle de lecture ─────────────────────────────────────────────
            try:
                active_cycle = self._read_cycle()
                self._update_engine_state()

                # DTC : lecture toutes les 30 itérations critiques
                dtcs: List[str] = []
                if self._iteration % OBD_CYCLE_OPTIONAL_EVERY == 0:
                    dtcs = self.get_dtc()
                    # Mémoriser pour les cycles intermédiaires
                    with self.state_lock:
                        self.shared_state["dtcs"] = dtcs
                else:
                    with self.state_lock:
                        dtcs = list(self.shared_state.get("dtcs", []))

                # Normalisation IA (uniquement si des données existent)
                ai_snapshot: Optional[Dict[str, Any]] = None
                if self._normalizer and self._live_snapshot:
                    safety_meta = self._pid_tracker.get_stats()
                    safety_meta["cycle_actuel"] = active_cycle
                    safety_meta["iteration"]    = self._iteration
                    safety_meta["erreurs_consecutives"] = self._global_errors
                    safety_meta["mode_degrade"] = self.is_degraded_mode
                    safety_meta["vehicle_state"] = self.vehicle_state
                    ai_snapshot = self._normalizer.normalize(
                        self._translate_for_normalizer(self._live_snapshot),
                        dtcs, meta=safety_meta
                    )

                # Mise à jour atomique du shared_state
                with self.state_lock:
                    self.shared_state["statut_obd"] = "connecté (dégradé)" if self.is_degraded_mode else "connecté"
                    self.shared_state["obd_data"]   = dict(self._live_snapshot)
                    if ai_snapshot:
                        self.shared_state["obd_snapshot_ia"] = ai_snapshot

                self._iteration += 1

            except Exception as e:
                logger.error(f"[OBD] Erreur inattendue dans la boucle : {e}")
                self._global_errors += 1
                if self._global_errors >= OBD_GLOBAL_ERROR_THRESHOLD:
                    self.connected = False

            # ── Pause inter-cycles ───────────────────────────────────────────
            wait_time = OBD_DEGRADED_MODE_INTERVAL if self.is_degraded_mode else OBD_CYCLE_CRITICAL_INTERVAL
            self.event_stop.wait(timeout=wait_time)

        # ── Nettoyage à l'arrêt ──────────────────────────────────────────────
        self._watchdog.stop()
        if self.connection and self.connection.status() != obd.OBDStatus.NOT_CONNECTED:
            try:
                self.connection.close()
            except Exception:
                pass
        logger.info("[OBD] Thread OBD arrêté proprement.")
