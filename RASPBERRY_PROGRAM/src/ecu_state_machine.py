from enum import Enum
import time
from typing import Dict, Any

class PowerState(Enum):
    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"

class LogicState(Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"

class ECUStateMachine:
    def __init__(self, event_bus, stability_delay_s: float = 3.0):
        self.power_state = PowerState.RUNNING  # RUNNING par défaut (pas de Power Manager actif)
        self.logic_state = LogicState.NORMAL
        
        self.target_logic_state = LogicState.NORMAL
        self.state_candidate_since = 0.0
        self.stability_delay_s = stability_delay_s
        
        # S'abonne aux événements du Power Manager
        self.event_bus = event_bus
        if self.event_bus:
            self.event_bus.subscribe("POWER_STATE_EVENT", self._on_power_state)

    def _on_power_state(self, data: Dict[str, Any]) -> None:
        """
        Met à jour l'état d'énergie interne à partir du bus d'événements.
        """
        self.power_state = data.get("power_state", PowerState.OFF)

    def update_logic_state(self, event: Dict[str, Any]) -> LogicState:
        """
        Gère la logique véhicule avec un hystérésis temporel (timestamps) pour éviter les oscillations.
        Événement structuré attendu : {"priority": int, "requires_stop": bool, "trend": str}
        """
        priority = event.get("priority", 4)
        requires_stop = event.get("requires_stop", False)
        trend = event.get("trend", "STABLE")
        
        proposed_state = LogicState.NORMAL
        
        # 1. Règle OR stricte de sécurité
        if priority == 1 or requires_stop or (trend == "WORSENING" and priority <= 2):
            proposed_state = LogicState.CRITICAL
        # 2. Règle Mode Dégradé
        elif priority == 2:
            proposed_state = LogicState.DEGRADED
            
        current_time = time.time()
        
        # 3. Logique de Stabilité (Hystérésis Temporel)
        if proposed_state == LogicState.CRITICAL:
            # Transition immédiate pour la sécurité
            self.logic_state = LogicState.CRITICAL
            self.target_logic_state = LogicState.CRITICAL
            self.state_candidate_since = current_time
        elif proposed_state != self.logic_state:
            if proposed_state == self.target_logic_state:
                # Vérifie si le délai d'hystérésis est dépassé
                if (current_time - self.state_candidate_since) >= self.stability_delay_s:
                    self.logic_state = proposed_state
                    self.state_candidate_since = current_time
            else:
                self.target_logic_state = proposed_state
                self.state_candidate_since = current_time
        else:
            self.target_logic_state = self.logic_state
            self.state_candidate_since = current_time
            
        return self.logic_state
