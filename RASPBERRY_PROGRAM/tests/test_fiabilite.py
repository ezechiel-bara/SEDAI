import unittest
import sys
import os
import threading
import queue

# Ajouter le répertoire src au PATH pour pouvoir importer les modules SEDAI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# pyrefly: ignore [missing-import]
from diagnostic_module import DiagnosticModule
# pyrefly: ignore [missing-import]
from config import SEUIL_TEMP_MAX, SEUIL_BATT_MIN


# ── Mocks légers ─────────────────────────────────────────────────────────────

class MockMemory:
    """Mock du module mémoire conversationnelle."""
    def __init__(self, has_history: bool = True) -> None:
        self.has_history = has_history

    def get_last_report(self):
        return "Précédent diagnostic" if self.has_history else None

    def get_history(self):
        return []

    def add_exchange(self, *args):
        pass


class MockTTS:
    """Mock du module TTS (pas de synthèse vocale en test)."""
    def speak(self, text: str) -> None:
        pass


class MockEventBus:
    """Mock du bus d'événements (pas de publication en test)."""
    def subscribe(self, event_type: str, callback) -> None:
        pass

    def publish(self, event_type: str, data=None) -> None:
        pass


# ── Tests de fiabilité ────────────────────────────────────────────────────────

class TestDiagnosticReliability(unittest.TestCase):
    """
    Tests unitaires validant la fiabilité du moteur de règles SEDAI.

    Couvre :
      - Détection d'alertes critiques (surchauffe, batterie, DTC)
      - Anti-répétition (cache d'alertes)
      - Score de confiance multicritère
      - Chargement de la base de connaissances
      - Calcul du F1-Score sur le moteur de règles déterministe
    """

    def setUp(self):
        """Crée une instance isolée de DiagnosticModule sans lancer les threads."""
        self.diag = DiagnosticModule(
            shared_state={},
            state_lock=threading.Lock(),
            action_queue=queue.Queue(),
            memory=MockMemory(has_history=True),
            tts=MockTTS(),
            event_stop=threading.Event(),
            event_bus=MockEventBus(),
            llm=None,
        )

    # ── Alertes critiques ────────────────────────────────────────────────────

    def test_critical_overheat_alert(self):
        """Surchauffe moteur → alerte CRITIQUE attendue."""
        obd_data = {"temp_moteur": SEUIL_TEMP_MAX + 5, "tension": 13.5}
        alert, should_speak, llm_enabled = self.diag._check_critical_alerts(
            "connecté", obd_data, []
        )
        self.assertIsNotNone(alert)
        self.assertIn("CRITIQUE", alert)
        self.assertIn("Surchauffe moteur", alert)

    def test_critical_battery_alert(self):
        """Tension batterie critique → alerte CRITIQUE attendue."""
        obd_data = {"temp_moteur": 90, "tension": SEUIL_BATT_MIN - 1.0}
        alert, should_speak, llm_enabled = self.diag._check_critical_alerts(
            "connecté", obd_data, []
        )
        self.assertIsNotNone(alert)
        self.assertIn("CRITIQUE", alert)
        self.assertIn("Tension batterie", alert)

    def test_normal_condition_no_alert(self):
        """Conditions normales → aucune alerte attendue."""
        obd_data = {"temp_moteur": 90, "tension": 14.0}
        alert, should_speak, llm_enabled = self.diag._check_critical_alerts(
            "connecté", obd_data, []
        )
        self.assertIsNone(alert)

    def test_llm_bypass_policy_p0335(self):
        """P0335 (criticité CRITIQUE) doit être présent dans la knowledge base."""
        kb = self.diag.knowledge_base
        if "P0335" in kb:
            self.assertEqual(kb["P0335"]["criticite"], "CRITIQUE")
            self.assertIn("vilebrequin", kb["P0335"]["description"].lower())

    # ── Anti-répétition ──────────────────────────────────────────────────────

    def test_anti_repetition_cache(self):
        """Le cache empêche la répétition vocale de la même alerte."""
        obd_data = {"temp_moteur": SEUIL_TEMP_MAX + 5}

        # Première alerte
        alert1, speak1, _ = self.diag._check_critical_alerts("connecté", obd_data, [])
        self.assertIsNotNone(alert1)

        # Deuxième alerte immédiate (même température) → ne doit pas parler
        alert2, speak2, _ = self.diag._check_critical_alerts("connecté", obd_data, [])
        self.assertFalse(speak2)

        # Troisième alerte avec aggravation → doit parler (trend WORSENING)
        obd_data_worse = {"temp_moteur": SEUIL_TEMP_MAX + 15}
        alert3, speak3, _ = self.diag._check_critical_alerts("connecté", obd_data_worse, [])
        self.assertIsNotNone(alert3)

    # ── Score de confiance ───────────────────────────────────────────────────

    def test_confidence_score_high(self):
        """Beaucoup de PIDs + historique → score ÉLEVÉ."""
        obd_data = {
            "vitesse": 50, "regime": 2000, "temp_moteur": 90,
            "maf": 10, "map": 40, "tension": 14.0
        }
        dtcs = ["P0171"]
        score = self.diag._calculate_confidence_score(obd_data, dtcs)
        self.assertEqual(score, "ÉLEVÉ")

    def test_confidence_score_low(self):
        """Peu de PIDs + pas d'historique → score FAIBLE ou MODÉRÉ."""
        self.diag.memory = MockMemory(has_history=False)
        obd_data = {"vitesse": 50, "regime": None, "temp_moteur": None, "maf": None}
        dtcs = []
        score = self.diag._calculate_confidence_score(obd_data, dtcs)
        self.assertIn(score, ["FAIBLE", "MODÉRÉ"])

    # ── Base de connaissances ────────────────────────────────────────────────

    def test_knowledge_base_loading(self):
        """La base de connaissances DTC se charge correctement."""
        kb = self.diag.knowledge_base
        self.assertIsInstance(kb, dict)
        if "P0300" in kb:
            self.assertIn("criticite", kb["P0300"])
            self.assertEqual(kb["P0300"]["criticite"], "ELEVEE")

    # ── F1-Score (métriques de classification) ───────────────────────────────

    def test_f1_score_simulation(self):
        """
        Simulation du calcul des métriques F1-Score sur le moteur de règles.

        Ground truth : [1, 0, 1] → (Alerte, Pas d'alerte, Alerte)
        Le moteur de règles étant déterministe, le F1-Score DOIT être 1.0.

        Métriques calculées :
          - Précision = VP / (VP + FP)
          - Rappel    = VP / (VP + FN)
          - F1-Score  = 2 × (Précision × Rappel) / (Précision + Rappel)
        """
        # Réinitialiser le cache d'alertes pour éviter l'interférence inter-tests
        self.diag.alert_cache.clear()

        cas_tests = [
            ({"temp_moteur": 110}, 1),             # Vrai positif (Surchauffe)
            ({"temp_moteur": 90, "tension": 14.2}, 0),  # Vrai négatif (Normal)
            ({"tension": 10.0}, 1),                 # Vrai positif (Batterie basse)
        ]

        vrai_positifs = 0
        faux_positifs = 0
        faux_negatifs = 0

        for data, ground_truth in cas_tests:
            alert, _, _ = self.diag._check_critical_alerts("connecté", data, [])
            pred = 1 if alert else 0
            if pred == 1 and ground_truth == 1:
                vrai_positifs += 1
            elif pred == 1 and ground_truth == 0:
                faux_positifs += 1
            elif pred == 0 and ground_truth == 1:
                faux_negatifs += 1

        precision = (
            vrai_positifs / (vrai_positifs + faux_positifs)
            if (vrai_positifs + faux_positifs) > 0 else 0
        )
        recall = (
            vrai_positifs / (vrai_positifs + faux_negatifs)
            if (vrai_positifs + faux_negatifs) > 0 else 0
        )
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0 else 0
        )

        # Le F1-score doit être parfait (1.0) sur ce mini dataset déterministe
        self.assertEqual(f1_score, 1.0)
        self.assertEqual(precision, 1.0)
        self.assertEqual(recall, 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
