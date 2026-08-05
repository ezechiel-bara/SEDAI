"""
obd_safety.py — Couche de sécurité OBD-II (SEDAI v2.1)

Rôle : protéger l'interface ELM327 contre la surcharge et
détecter les comportements anormaux de l'adaptateur.

Ce module ne contient AUCUNE logique métier OBD :
il s'intercale entre le code d'acquisition et le bus ELM327.

Composants :
  - RateLimiter       : impose un délai minimum entre deux requêtes PID
  - PIDHealthTracker  : désactive les PIDs systématiquement défaillants
  - ELM327Watchdog    : détecte les freezes silencieux de l'adaptateur
"""

import logging
import time
from typing import Dict, Optional

from config import (
    OBD_INTER_PID_DELAY,
    OBD_PID_ERROR_THRESHOLD,
    OBD_WATCHDOG_TIMEOUT,
)

logger = logging.getLogger("OBD.Safety")


# ══════════════════════════════════════════════════════════════════════════════
# Rate Limiter
# ══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Impose un délai minimum entre deux requêtes PID consécutives.

    L'ELM327 clone possède un buffer UART fragile :
    sans délai inter-requêtes, les réponses peuvent se mélanger
    et provoquer des timeouts en cascade.

    Usage :
        limiter = RateLimiter()
        limiter.wait()          # bloque si le délai n'est pas écoulé
        response = query_pid()
        limiter.record()        # enregistre l'horodatage de la requête
    """

    def __init__(self, min_delay_s: float = OBD_INTER_PID_DELAY) -> None:
        self._min_delay = min_delay_s
        self._last_query_time: float = 0.0

    def wait(self) -> None:
        """
        Attend si nécessaire pour respecter le délai inter-requêtes.
        Appeler AVANT chaque query_pid().
        """
        elapsed = time.monotonic() - self._last_query_time
        remaining = self._min_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def record(self) -> None:
        """
        Enregistre l'instant de la dernière requête envoyée.
        Appeler APRÈS chaque query_pid(), qu'elle ait réussi ou non.
        """
        self._last_query_time = time.monotonic()


# ══════════════════════════════════════════════════════════════════════════════
# PID Health Tracker
# ══════════════════════════════════════════════════════════════════════════════

class PIDHealthTracker:
    """
    Suit le taux de succès/échec de chaque PID interrogé.

    Un PID qui échoue systématiquement (non supporté par l'ECU,
    ou firmware ELM défaillant) est automatiquement mis en quarantaine
    pour éviter les timeouts répétitifs inutiles.

    La quarantaine est temporaire : le PID est réactivé après un
    cycle de reconnexion ou un reset explicite.
    """

    def __init__(self, error_threshold: int = OBD_PID_ERROR_THRESHOLD) -> None:
        self._error_threshold = error_threshold
        # {pid_name: consecutive_error_count}
        self._error_counts: Dict[str, int] = {}
        # PIDs désactivés après dépassement du seuil
        self._disabled_pids: set = set()

    def record_success(self, pid_name: str) -> None:
        """Réinitialise le compteur d'erreurs pour ce PID."""
        self._error_counts[pid_name] = 0
        # Un succès réhabilite un PID (cas où l'ECU répond à nouveau)
        self._disabled_pids.discard(pid_name)

    def record_failure(self, pid_name: str) -> None:
        """
        Incrémente le compteur d'erreurs.
        Désactive le PID si le seuil est atteint.
        """
        count = self._error_counts.get(pid_name, 0) + 1
        self._error_counts[pid_name] = count

        if count >= self._error_threshold:
            if pid_name not in self._disabled_pids:
                logger.warning(
                    f"[Safety] PID '{pid_name}' désactivé après "
                    f"{count} échecs consécutifs (non supporté ou timeout)."
                )
                self._disabled_pids.add(pid_name)

    def is_active(self, pid_name: str) -> bool:
        """Retourne True si le PID est autorisé à être interrogé."""
        return pid_name not in self._disabled_pids

    def reset(self) -> None:
        """
        Réinitialise tous les compteurs et réactive tous les PIDs.
        À appeler après une reconnexion OBD réussie.
        """
        self._error_counts.clear()
        self._disabled_pids.clear()
        logger.info("[Safety] PID health tracker réinitialisé (reconnexion).")

    def get_stats(self) -> Dict[str, object]:
        """Retourne un résumé de l'état de santé des PIDs."""
        return {
            "pids_actifs": len(self._error_counts) - len(self._disabled_pids),
            "pids_desactives": len(self._disabled_pids),
            "liste_desactives": sorted(self._disabled_pids),
        }


# ══════════════════════════════════════════════════════════════════════════════
# ELM327 Watchdog
# ══════════════════════════════════════════════════════════════════════════════

class ELM327Watchdog:
    """
    Détecte les freezes silencieux de l'interface ELM327.

    Un ELM327 clone peut se bloquer sans signaler d'erreur explicite :
    il cesse simplement de répondre aux commandes OBD.
    Le watchdog impose une durée maximale sans réponse valide.

    Usage :
        watchdog = ELM327Watchdog()
        watchdog.start()                # démarre le chrono
        watchdog.record_valid_response()  # appeler à chaque réponse utile
        if watchdog.is_frozen():        # vérifier périodiquement
            reconnect()
    """

    def __init__(self, timeout_s: float = OBD_WATCHDOG_TIMEOUT) -> None:
        self._timeout_s = timeout_s
        self._last_valid_response: float = time.monotonic()
        self._started: bool = False

    def start(self) -> None:
        """Démarre le watchdog (à appeler après une connexion réussie)."""
        self._last_valid_response = time.monotonic()
        self._started = True
        logger.debug(
            f"[Safety] Watchdog ELM327 démarré (timeout={self._timeout_s}s)."
        )

    def record_valid_response(self) -> None:
        """
        Signale qu'une réponse valide vient d'être reçue.
        Doit être appelé à chaque query_pid() qui retourne une valeur non-null.
        """
        self._last_valid_response = time.monotonic()

    def is_frozen(self) -> bool:
        """
        Retourne True si aucune réponse valide n'a été reçue
        depuis plus de `timeout_s` secondes.

        Note : ne signale un freeze que si le watchdog a été démarré,
        pour éviter les faux positifs pendant la phase d'initialisation.
        """
        if not self._started:
            return False
        elapsed = time.monotonic() - self._last_valid_response
        if elapsed > self._timeout_s:
            logger.error(
                f"[Safety] Freeze ELM327 détecté : aucune réponse depuis "
                f"{elapsed:.0f}s (seuil={self._timeout_s}s). "
                "Reconnexion requise."
            )
            return True
        return False

    def stop(self) -> None:
        """Désactive le watchdog (arrêt propre du thread)."""
        self._started = False

    def time_since_last_response(self) -> Optional[float]:
        """Retourne le nombre de secondes depuis la dernière réponse valide."""
        if not self._started:
            return None
        return time.monotonic() - self._last_valid_response


# ══════════════════════════════════════════════════════════════════════════════
# Backoff Calculator
# ══════════════════════════════════════════════════════════════════════════════

class BackoffCalculator:
    """
    Calcule le délai de reconnexion avec croissance exponentielle plafonnée.

    Évite de saturer le port série (et de perturber l'ELM327)
    avec des tentatives de reconnexion trop rapprochées.

    Exemple avec base=5, factor=2, max=120 :
      tentative 1 → 5s, 2 → 10s, 3 → 20s, 4 → 40s, 5+ → 120s
    """

    def __init__(
        self,
        base_s: float,
        factor: float,
        max_s: float,
    ) -> None:
        self._base = base_s
        self._factor = factor
        self._max = max_s
        self._attempt: int = 0

    def next_delay(self) -> float:
        """Retourne le délai pour la prochaine tentative et incrémente le compteur."""
        delay = min(self._base * (self._factor ** self._attempt), self._max)
        self._attempt += 1
        return delay

    def reset(self) -> None:
        """Remet le compteur à zéro après une connexion réussie."""
        self._attempt = 0

    @property
    def attempt_count(self) -> int:
        return self._attempt
