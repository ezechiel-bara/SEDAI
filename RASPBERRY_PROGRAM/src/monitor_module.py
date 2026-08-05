"""
monitor_module.py — Surveillance silencieuse en conduite (SEDAI v2.0)
Tourne en tâche de fond et analyse les données OBD partagées toutes les X secondes.
Détecte les anomalies sur les seuils standards ET étendus (transmission, fuel trim).
S'il détecte une anomalie critique, il pousse une requête dans la file d'actions
pour déclencher un diagnostic IA automatique.
"""

import logging
import threading
import time
import queue
from typing import Any, Dict

from config import (
    MONITOR_INTERVAL,
    SEUIL_TEMP_MAX,
    SEUIL_RPM_MAX, SEUIL_RPM_DUREE,
    SEUIL_CHARGE_MAX, SEUIL_CHARGE_DUREE,
    SEUIL_BATT_MIN, SEUIL_BATT_MAX,
    SEUIL_CARBURANT,
    SEUIL_TEMP_TRANSMISSION_MAX,
    SEUIL_FUEL_TRIM_DEVIATION,
)

# Logger dédié à ce module
logger = logging.getLogger("MONITOR")


class MonitorModule(threading.Thread):
    """
    Module vérifiant toutes les MONITOR_INTERVAL secondes l'état des constantes du véhicule.

    Ne prend pas la parole sauf en cas de défaut critique, auquel cas il lance
    une requête de diagnostic d'urgence au module IA. Analyse les seuils standards
    (température moteur, RPM, batterie, charge) et les seuils étendus
    (température transmission, ajustements carburant STFT/LTFT).
    """

    def __init__(
        self,
        shared_state: Dict[str, Any],
        state_lock: threading.Lock,
        action_queue: queue.Queue,
        event_stop: threading.Event,
    ) -> None:
        """
        Initialise le module de surveillance.

        Args:
            shared_state: Dictionnaire partagé contenant les données OBD temps réel.
            state_lock: Verrou pour la lecture de shared_state.
            action_queue: File dans laquelle pousser les requêtes de diagnostic.
            event_stop: Événement d'arrêt global.
        """
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.state_lock = state_lock
        self.action_queue = action_queue
        self.event_stop = event_stop

        # Suivi temporel pour les dépassements nécessitant une durée minimum
        self.rpm_high_since: float | None = None
        self.charge_high_since: float | None = None
        
        # Cooldown anti-spam : éviter de saturer l'IA avec la même alerte
        self.last_alert_time: float = 0.0
        self.ALERT_COOLDOWN: float = 300.0  # 5 minutes de silence par défaut

        # Suivi des DTC connus pour ne déclencer qu'aux nouveaux
        self.known_dtcs: set = set()
        self.first_pass_done: bool = False

    def check_anomalies(self, data: Dict[str, Any], current_dtcs: list) -> None:
        """
        Évalue l'ensemble des règles et seuils d'anomalies.

        Vérifie les seuils standards (température moteur, RPM, batterie, charge,
        carburant) ainsi que les seuils étendus (température transmission, STFT,
        LTFT). En cas d'anomalie confirmée, pousse un diagnostic_request dans
        la file d'actions.

        Args:
            data: Données OBD en temps réel (issues de shared_state["obd_data"]).
            current_dtcs: Liste des DTC actuels remontés par l'ECU.
        """
        context_anomalie = []
        now = time.time()

        # ── 1. Température moteur ───────────────────────────────────────────
        temp = data.get("temp_moteur")
        if temp is not None and temp > SEUIL_TEMP_MAX:
            context_anomalie.append(f"Surchauffe moteur détectée : {temp}°C.")

        # ── 2. Régime moteur (avec durée minimum) ───────────────────────────
        rpm = data.get("regime")
        if rpm is not None and rpm > SEUIL_RPM_MAX:
            if self.rpm_high_since is None:
                self.rpm_high_since = now
            elif (now - self.rpm_high_since) > SEUIL_RPM_DUREE:
                context_anomalie.append(f"Surrégime moteur prolongé : {rpm} RPM.")
                self.rpm_high_since = None  # Réarmement après déclenchement
        else:
            self.rpm_high_since = None

        # ── 3. Tension batterie ─────────────────────────────────────────────
        batt = data.get("tension")
        if batt is not None:
            if batt < SEUIL_BATT_MIN:
                context_anomalie.append(f"Tension batterie anormalement basse : {batt} V.")
            elif batt > SEUIL_BATT_MAX:
                context_anomalie.append(f"Surtension alternateur/batterie détectée : {batt} V.")

        # ── 4. Charge moteur (avec durée minimum) ───────────────────────────
        charge = data.get("charge")
        if charge is not None and charge > SEUIL_CHARGE_MAX:
            if self.charge_high_since is None:
                self.charge_high_since = now
            elif (now - self.charge_high_since) > SEUIL_CHARGE_DUREE:
                context_anomalie.append(f"Forte charge moteur prolongée : {charge}%.")
                self.charge_high_since = None
        else:
            self.charge_high_since = None

        # ── 5. Niveau carburant critque ─────────────────────────────────────
        carburant = data.get("carburant")
        if carburant is not None and carburant < SEUIL_CARBURANT:
            context_anomalie.append(f"Niveau de carburant critique : {carburant}%.")

        # ── 6. Nouveaux DTC ─────────────────────────────────────────────────
        current_dtcs_set = set(current_dtcs)
        if not self.first_pass_done:
            self.known_dtcs = current_dtcs_set
            self.first_pass_done = True
        else:
            new_dtcs = current_dtcs_set - self.known_dtcs
            if new_dtcs:
                context_anomalie.append(
                    f"Nouveaux codes défauts détectés : {', '.join(new_dtcs)}."
                )
                self.known_dtcs = current_dtcs_set

        # ── 7. Température de transmission (étendu) ─────────────────────────
        temp_trans = data.get("temp_transmission")
        if temp_trans is not None and temp_trans > SEUIL_TEMP_TRANSMISSION_MAX:
            context_anomalie.append(
                f"Surchauffe du système de transmission détectée : {temp_trans}°C."
            )

        # ── 8. Ajustement carburant court terme STFT (étendu) ───────────────
        stft = data.get("stft_b1")
        if stft is not None and abs(stft) > SEUIL_FUEL_TRIM_DEVIATION:
            context_anomalie.append(
                f"Déviation anormale de l'alimentation en carburant détectée : {stft}%."
            )

        # ── 9. Ajustement carburant long terme LTFT (étendu) ────────────────
        ltft = data.get("ltft_b1")
        if ltft is not None and abs(ltft) > SEUIL_FUEL_TRIM_DEVIATION:
            context_anomalie.append(
                f"Déréglage persistant du système d'alimentation détecté : {ltft}%."
            )

        # --- Rapport de statut périodique à l'écran ---
        with self.state_lock:
            dtcs_confirmes  = list(self.shared_state.get("dtcs_confirmes", []))
            dtcs_en_attente = list(self.shared_state.get("dtcs_en_attente", []))
            dtcs_permanents = list(self.shared_state.get("dtcs_permanents", []))

        # Construction du libellé des DTCs par catégorie
        parts = []
        if dtcs_confirmes:
            parts.append(f"Confirmés : {dtcs_confirmes}")
        if dtcs_en_attente:
            parts.append(f"En attente : {dtcs_en_attente}")
        if dtcs_permanents:
            parts.append(f"Permanents : {dtcs_permanents}")
        
        dtc_details = " | ".join(parts) if parts else "Aucun"

        logger.info(
            f"[MONITOR] Rapport périodique — RPM : {rpm if rpm is not None else 'N/A'} | "
            f"Temp Moteur : {temp if temp is not None else 'N/A'}°C | "
            f"Tension : {batt if batt is not None else 'N/A'}V | "
            f"DTCs : {dtc_details}"
        )

        # ── Déclenchement diagnostic si anomalie confirmée ──────────────────
        if context_anomalie:
            if (now - self.last_alert_time) < self.ALERT_COOLDOWN:
                logger.debug(f"[MONITOR] Bloqué par l'anti-spam (cooldown actif) : {context_anomalie}")
            else:
                phrase = "Anomalies automatiques identifiées : " + " ".join(context_anomalie)
                logger.warning(f"[MONITOR] {phrase}")
                self.action_queue.put({
                    "type": "diagnostic_request",
                    "source": "monitor",
                    "context": phrase
                })
                self.last_alert_time = now # Réamorcage du chrono de silence
        else:
            logger.debug(f"[MONITOR] Données analysées — aucune anomalie : {data}")

    def run(self) -> None:
        """
        Boucle du thread : inspecte périodiquement les seuils d'anomalie.

        Attend MONITOR_INTERVAL secondes entre chaque vérification, avec
        possibilité d'être réveillé proprement via event_stop.
        """
        logger.info("[MONITOR] Démarrage du thread de surveillance.")

        while not self.event_stop.is_set():
            # Attente interruptible de MONITOR_INTERVAL secondes
            if self.event_stop.wait(MONITOR_INTERVAL):
                break

            with self.state_lock:
                obd_status = self.shared_state.get("statut_obd", "déconnecté")
                live_data = dict(self.shared_state.get("obd_data", {}))
                dtc_list = list(self.shared_state.get("dtcs", []))

            if obd_status == "connecté" and live_data:
                self.check_anomalies(live_data, dtc_list)

        logger.info("[MONITOR] Arrêt du thread de surveillance.")
