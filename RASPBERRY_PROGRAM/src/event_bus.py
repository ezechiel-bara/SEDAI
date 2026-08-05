"""
event_bus.py — Bus d'événements inter-modules pour SEDAI (v2.0)
Implémente un patron publish/subscribe thread-safe via threading.Lock.
Permet le découplage complet entre les modules (OBD, Diagnostic, Power, etc.).
"""

import logging
import threading
from typing import Any, Callable, Dict, List

logger = logging.getLogger("EVENT_BUS")


class EventBus:
    """Bus d'événements publish/subscribe thread-safe.

    Chaque module peut s'abonner à un type d'événement et en publier.
    Les callbacks sont appelés dans le thread du publisher.

    Example:
        bus = EventBus()
        bus.subscribe("DTC_EVENT", my_handler)
        bus.publish("DTC_EVENT", {"priority": 1})
    """

    def __init__(self) -> None:
        """Initialise le bus avec un registre vide et un verrou de protection."""
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Enregistre un callback pour un type d'événement donné.

        Args:
            event_type: Identifiant de l'événement (ex: "DTC_EVENT").
            callback: Fonction appelée lors de la publication. Doit accepter un dict.
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
        logger.debug(f"[EVENT_BUS] Abonnement : {callback.__qualname__} → {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Retire un callback d'un type d'événement.

        Args:
            event_type: Identifiant de l'événement.
            callback: Callback à retirer.
        """
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass

    def publish(self, event_type: str, data: Any = None) -> None:
        """Publie un événement vers tous les abonnés enregistrés.

        Les callbacks sont appelés de manière synchrone dans le thread courant.
        Chaque exception levée par un callback est capturée et loggée
        sans interrompre les autres abonnés.

        Args:
            event_type: Identifiant de l'événement.
            data: Payload transmis aux callbacks (généralement un dict).
        """
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        for callback in callbacks:
            try:
                callback(data)
            except Exception as exc:
                logger.error(
                    f"[EVENT_BUS] Erreur callback '{callback.__qualname__}' "
                    f"pour '{event_type}' : {exc}"
                )
