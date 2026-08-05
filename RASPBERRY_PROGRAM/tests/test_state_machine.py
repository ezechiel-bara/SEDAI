import unittest
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# pyrefly: ignore [missing-import]
from ecu_state_machine import ECUStateMachine, PowerState, LogicState


class MockEventBus:
    """Mock du bus d'événements (pas de publication en test)."""
    def subscribe(self, event_type: str, callback) -> None:
        pass

    def publish(self, event_type: str, data=None) -> None:
        pass


class TestECUStateMachine(unittest.TestCase):
    """
    Tests unitaires de la machine à états ECU.

    Couvre :
      - Transition immédiate vers CRITICAL (sécurité)
      - Hystérésis temporel pour les transitions DEGRADED
      - Stabilité de l'état quand le même événement est répété
    """

    def setUp(self):
        """Crée une state machine avec hystérésis court de 0.5s pour les tests."""
        self.sm = ECUStateMachine(
            event_bus=MockEventBus(),
            stability_delay_s=0.5,
        )

    def test_initial_state(self):
        """L'état initial est RUNNING + NORMAL."""
        self.assertEqual(self.sm.power_state, PowerState.RUNNING)
        self.assertEqual(self.sm.logic_state, LogicState.NORMAL)

    def test_logic_state_critical_immediate(self):
        """Priorité 1 → transition IMMÉDIATE vers CRITICAL (pas d'hystérésis)."""
        event = {"priority": 1, "requires_stop": False, "trend": "STABLE"}
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.CRITICAL)

    def test_logic_state_critical_on_requires_stop(self):
        """requires_stop=True → transition IMMÉDIATE vers CRITICAL."""
        self.sm = ECUStateMachine(event_bus=MockEventBus())
        event = {"priority": 3, "requires_stop": True, "trend": "STABLE"}
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.CRITICAL)

    def test_logic_state_critical_on_worsening(self):
        """trend=WORSENING + priorité ≤ 2 → CRITICAL immédiat."""
        event = {"priority": 2, "requires_stop": False, "trend": "WORSENING"}
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.CRITICAL)

    def test_logic_state_stability_hysteresis(self):
        """Priorité 2 → DEGRADED uniquement après hystérésis temporel (0.5s)."""
        event = {"priority": 2, "requires_stop": False, "trend": "STABLE"}

        # t=0 : l'état demandé est DEGRADED mais la stabilité force NORMAL
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.NORMAL)

        # t=0.2s : toujours sous le seuil d'hystérésis (0.5s)
        time.sleep(0.2)
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.NORMAL)

        # t=0.6s : le seuil d'hystérésis est dépassé → transition autorisée
        time.sleep(0.4)
        state = self.sm.update_logic_state(event)
        self.assertEqual(state, LogicState.DEGRADED)

    def test_logic_state_returns_to_normal(self):
        """Après une alerte critique, retour à NORMAL si priorité > 2 (avec hystérésis)."""
        # D'abord passer en CRITICAL
        critical = {"priority": 1, "requires_stop": False, "trend": "STABLE"}
        self.sm.update_logic_state(critical)
        self.assertEqual(self.sm.logic_state, LogicState.CRITICAL)

        # Envoyer un événement NORMAL (priorité 4)
        normal = {"priority": 4, "requires_stop": False, "trend": "STABLE"}
        self.sm.update_logic_state(normal)
        # Pas encore NORMAL (hystérésis)

        time.sleep(0.6)
        state = self.sm.update_logic_state(normal)
        self.assertEqual(state, LogicState.NORMAL)


if __name__ == '__main__':
    unittest.main(verbosity=2)
