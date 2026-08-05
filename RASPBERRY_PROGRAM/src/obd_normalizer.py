"""
obd_normalizer.py — Normalisation et Feature Engineering OBD-II (SEDAI v2.1.1)

Rôle : transformer les données OBD brutes (dict de valeurs numériques)
en un snapshot JSON structuré, prêt à être consommé par un modèle LLM local.

Pipeline interne :
  raw_data → OBDDataValidator (clamp / NaN / plausibilité)
           → OBDNormalizer    (structuration + feature engineering)
           → dict JSON-ready

Corrections v2.1.1 :
  - Pollution RPM history : slicing garanti [-N:] + guard None explicite
  - Type safety : isinstance(val, (int, float)) avant tout opérateur > < abs()
  - Score de risque : normalisation exponentielle (1 - exp(-x)) — progression réaliste
  - tension_normale : toujours bool (plus jamais None)
  - OBDDataValidator : couche de validation stricte avant normalisation
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("OBD.Normalizer")


# ══════════════════════════════════════════════════════════════════════════════
# Schéma des PIDs
# ══════════════════════════════════════════════════════════════════════════════

# plausible : (min_hard, max_hard) — valeurs hors plage = clamping ou rejet
# normal    : (min_ok, max_ok)     — plage "sain" pour le score de risque
_PID_SCHEMA: Dict[str, Dict[str, Any]] = {
    "regime":             {"label": "Régime moteur",                "unit": "RPM",  "plausible": (0, 9000),    "normal": (600, 6500)},
    "temp_moteur":        {"label": "Température moteur",           "unit": "°C",   "plausible": (-40, 200),   "normal": (70, 105)},
    "tension":            {"label": "Tension batterie/alternateur", "unit": "V",    "plausible": (0, 20),      "normal": (11.8, 15.2)},
    "vitesse":            {"label": "Vitesse",                      "unit": "km/h", "plausible": (0, 350),     "normal": (0, 250)},
    "charge":             {"label": "Charge moteur",                "unit": "%",    "plausible": (0, 100),     "normal": (0, 90)},
    "maf":                {"label": "Débit air (MAF)",              "unit": "g/s",  "plausible": (0, 500),     "normal": (0, 30)},
    "map":                {"label": "Pression admission (MAP)",     "unit": "kPa",  "plausible": (10, 300),    "normal": (20, 105)},
    "stft_b1":            {"label": "Correction court terme (STFT B1)", "unit": "%","plausible": (-100, 100),  "normal": (-15, 15)},
    "ltft_b1":            {"label": "Correction long terme (LTFT B1)", "unit": "%", "plausible": (-100, 100),  "normal": (-15, 15)},
    "papillon":           {"label": "Position papillon",            "unit": "%",    "plausible": (0, 100),     "normal": (0, 100)},
    "avance":             {"label": "Avance allumage",              "unit": "°",    "plausible": (-20, 60),    "normal": (0, 35)},
    "temp_admission":     {"label": "Température admission",        "unit": "°C",   "plausible": (-40, 90),    "normal": (-20, 60)},
    "pression_huile":     {"label": "Pression huile moteur",        "unit": "kPa",  "plausible": (0, 1000),    "normal": (200, 600)},
    "pression_carburant": {"label": "Pression carburant",           "unit": "kPa",  "plausible": (0, 800),     "normal": None},
    "carburant":          {"label": "Niveau carburant",             "unit": "%",    "plausible": (0, 100),     "normal": (10, 100)},
    "lambda":             {"label": "Sonde lambda (B1S1)",          "unit": "V",    "plausible": (0, 5),       "normal": (0.1, 0.9)},
    "temp_transmission":  {"label": "Température transmission",     "unit": "°C",   "plausible": (-40, 200),   "normal": (50, 120)},
}


# ══════════════════════════════════════════════════════════════════════════════
# OBD Data Validator
# ══════════════════════════════════════════════════════════════════════════════

class OBDDataValidator:
    """
    Couche de validation stricte des données OBD avant normalisation.

    Rôle : intercepter les valeurs corrompues produites par les ELM327 clones
    (NaN, Inf, string, hors plage matérielle) avant qu'elles n'atteignent
    le normalizer ou le LLM.

    Actions :
      - Reject    : valeur non numérique, NaN, Inf → supprimée du dict
      - Clamp     : valeur hors plage physique (plausible) → clamping avec warning
      - Pass      : valeur valide et dans la plage → inchangée

    Ce composant est stateless et ne produit aucun side-effect.
    """

    def validate(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Valide et nettoie le dictionnaire OBD brut.

        Args:
            raw_data : dict produit par obd_module (_live_snapshot)

        Returns:
            Dict filtré : uniquement des float valides dans la plage physique.
        """
        clean: Dict[str, float] = {}

        for key, value in raw_data.items():
            result = self._validate_value(key, value)
            if result is not None:
                clean[key] = result

        return clean

    def _validate_value(self, key: str, value: Any) -> Optional[float]:
        """
        Valide une valeur individuelle.

        Returns:
            float nettoyé, ou None si la valeur doit être rejetée.
        """
        # 1. Conversion en float
        try:
            f = float(value)
        except (TypeError, ValueError):
            logger.debug(
                f"[Validator] '{key}' rejeté : non convertible en float ({value!r})"
            )
            return None

        # 2. Détection NaN / Inf (ELM327 clones peuvent produire des réponses corrompues)
        if not math.isfinite(f):
            logger.warning(
                f"[Validator] '{key}' rejeté : valeur non-finie ({f!r})"
            )
            return None

        # 3. Vérification des plages physiques (clamp ou rejet)
        schema = _PID_SCHEMA.get(key)
        if schema and schema.get("plausible"):
            lo, hi = schema["plausible"]
            if f < lo or f > hi:
                # Clamp avec warning — ne pas rejeter, l'IA doit savoir
                clamped = max(lo, min(hi, f))
                logger.warning(
                    f"[Validator] '{key}' clamped : {f:.2f} → {clamped:.2f} "
                    f"(hors plage physique [{lo}, {hi}])"
                )
                return round(clamped, 2)

        return round(f, 2)


# ══════════════════════════════════════════════════════════════════════════════
# OBD Normalizer
# ══════════════════════════════════════════════════════════════════════════════

class OBDNormalizer:
    """
    Transforme un snapshot de données OBD validées en JSON AI-ready.

    Features calculées :
      - moteur_en_marche      : bool (RPM > 400)
      - moteur_chaud          : bool (temp_moteur > 75°C)
      - vehicule_arrete       : bool (vitesse < 2)
      - stabilite_regime      : str  (stable / légèrement_instable / instable / inconnu)
      - tension_normale       : bool (toujours, jamais None)
      - indicateur_risque     : str  (faible / modéré / élevé / critique)
      - score_risque          : float [0.0 – 1.0], normalisé via 1 - exp(-x)
      - nb_dtcs_actifs        : int
    """

    def __init__(self, vehicle_info: Optional[Dict[str, str]] = None) -> None:
        self._vehicle_info = vehicle_info or {}
        self._validator = OBDDataValidator()

        # Buffer circulaire glissant pour la stabilité RPM
        # Taille fixe, slicé garantie [-N:] à chaque mise à jour
        self._rpm_history: List[float] = []
        self._RPM_HISTORY_SIZE = 5

    # ── Méthode principale ────────────────────────────────────────────────────

    def normalize(
        self,
        raw_data: Dict[str, Any],
        dtcs: List[str],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produit le snapshot JSON complet prêt pour le LLM.

        Pipeline interne :
          1. Validation (OBDDataValidator) → rejette NaN / hors-plage
          2. Structuration des données ({label, valeur, unite})
          3. Feature engineering IA
          4. Assemblage du snapshot final

        Args:
            raw_data : dict OBD brut (_live_snapshot depuis obd_module)
            dtcs     : liste des codes défauts actifs
            meta     : informations optionnelles sur le cycle

        Returns:
            Dict sérialisable JSON — aucune valeur None ni HEX.
        """
        # 1. Validation stricte avant toute chose
        clean_data = self._validator.validate(raw_data)

        # 2. Structuration données
        donnees = self._build_donnees(clean_data)

        # 3. Feature engineering (sur données validées uniquement)
        features = self._compute_features(clean_data, dtcs)

        return {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vehicule":  self._format_vehicle(),
            "donnees":   donnees,
            "features_ia": features,
            "dtcs":      dtcs if dtcs else [],
            "meta":      meta or {},
        }

    # ── Construction du bloc données ──────────────────────────────────────────

    def _build_donnees(self, clean_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Convertit chaque valeur validée en {label, valeur, unite}.
        Uniquement les PIDs présents dans le schéma sont inclus.
        """
        donnees: Dict[str, Any] = {}
        for key, schema in _PID_SCHEMA.items():
            value = clean_data.get(key)
            if value is None:
                continue
            donnees[key] = {
                "label":  schema["label"],
                "valeur": value,
                "unite":  schema["unit"],
            }
        return donnees

    # ── Feature Engineering ───────────────────────────────────────────────────

    def _compute_features(
        self,
        clean_data: Dict[str, float],
        dtcs: List[str],
    ) -> Dict[str, Any]:
        """
        Calcule les features IA à partir des données validées.

        Toutes les valeurs extraites sont garanties float (passé par OBDDataValidator).
        Les gardes isinstance() restent présentes pour la robustesse défensive.
        """
        rpm     = clean_data.get("regime")
        temp    = clean_data.get("temp_moteur")
        vitesse = clean_data.get("vitesse")
        tension = clean_data.get("tension")
        stft    = clean_data.get("stft_b1")
        ltft    = clean_data.get("ltft_b1")
        charge  = clean_data.get("charge")

        # ── Booleans de base ─────────────────────────────────────────────────

        moteur_en_marche = (
            isinstance(rpm, (int, float)) and rpm > 400
        )
        moteur_chaud = (
            isinstance(temp, (int, float)) and temp > 75
        )
        vehicule_arrete = (
            not isinstance(vitesse, (int, float)) or vitesse < 2
        )

        # FIX : tension_normale est toujours bool, jamais None
        tension_normale: bool = (
            isinstance(tension, (int, float)) and (11.8 <= tension <= 15.2)
        )

        # ── Stabilité régime ─────────────────────────────────────────────────
        stabilite = self._compute_rpm_stability(rpm)

        # ── Score de risque ───────────────────────────────────────────────────
        score, niveau = self._compute_risk(rpm, temp, tension, charge, stft, ltft, dtcs)

        return {
            "moteur_en_marche":  moteur_en_marche,
            "moteur_chaud":      moteur_chaud,
            "vehicule_arrete":   vehicule_arrete,
            "tension_normale":   tension_normale,
            "stabilite_regime":  stabilite,
            "indicateur_risque": niveau,
            "score_risque":      round(score, 3),
            "nb_dtcs_actifs":    len(dtcs),
        }

    def _compute_rpm_stability(self, rpm: Optional[float]) -> str:
        """
        Évalue la stabilité du régime moteur sur une fenêtre glissante.

        FIX v2.1.1 :
          - Guard None explicite (on ne pollue pas l'historique avec un None)
          - Slicing garanti [-N:] pour éviter la croissance infinie de la liste

        Stable          : écart-type < 150 RPM
        Légèrement inst.: écart-type < 400 RPM
        Instable        : écart-type >= 400 RPM
        """
        # Guard None : on ne pollue pas l'historique si RPM absent (ELM freeze)
        if not isinstance(rpm, (int, float)):
            return "inconnu"

        self._rpm_history.append(float(rpm))
        # Slicing garanti : la liste ne dépasse jamais _RPM_HISTORY_SIZE éléments
        self._rpm_history = self._rpm_history[-self._RPM_HISTORY_SIZE:]

        if len(self._rpm_history) < 3:
            return "inconnu"

        avg = sum(self._rpm_history) / len(self._rpm_history)
        variance = sum((x - avg) ** 2 for x in self._rpm_history) / len(self._rpm_history)
        std_dev = variance ** 0.5

        if std_dev < 150:
            return "stable"
        elif std_dev < 400:
            return "légèrement_instable"
        else:
            return "instable"

    @staticmethod
    def _compute_risk(
        rpm:     Optional[float],
        temp:    Optional[float],
        tension: Optional[float],
        charge:  Optional[float],
        stft:    Optional[float],
        ltft:    Optional[float],
        dtcs:    List[str],
    ) -> Tuple[float, str]:
        """
        Calcule un score de risque avec normalisation exponentielle.

        FIX v2.1.1 — deux corrections majeures :

        1. Type safety : chaque comparaison est précédée de isinstance()
           → évite les erreurs de type si une valeur non numérique passe le validator

        2. Normalisation exponentielle :
           score_final = 1 - exp(-raw_score)
           → la courbe commence forte mais plafonne progressivement
           → évite l'effet "tout critique dès 2 problèmes" de min(score, 1.0)

        Exemple de progression :
           raw 0.10 → final 0.095   (faible)
           raw 0.40 → final 0.330   (modéré)
           raw 0.80 → final 0.551   (élevé)
           raw 1.50 → final 0.777   (critique)
           raw 2.50 → final 0.918   (très critique)

        Returns:
            Tuple (score_normalisé: float [0.0–1.0], niveau: str)
        """
        raw = 0.0  # score brut non normalisé (peut dépasser 1.0 par accumulation)

        # Température moteur
        if isinstance(temp, (int, float)):
            if temp > 105:
                raw += 0.60
            elif temp > 100:
                raw += 0.40
            elif temp > 95:
                raw += 0.20

        # Régime moteur excessif
        if isinstance(rpm, (int, float)):
            if rpm > 6500:
                raw += 0.40
            elif rpm > 5500:
                raw += 0.15

        # Tension batterie/alternateur
        if isinstance(tension, (int, float)):
            if tension < 11.5 or tension > 15.5:
                raw += 0.35
            elif tension < 12.0 or tension > 15.0:
                raw += 0.15

        # Charge moteur prolongée
        if isinstance(charge, (int, float)):
            if charge > 95:
                raw += 0.25
            elif charge > 85:
                raw += 0.10

        # Corrections carburant aberrantes (court terme)
        if isinstance(stft, (int, float)):
            if abs(stft) > 20:
                raw += 0.25
            elif abs(stft) > 15:
                raw += 0.10

        # Corrections carburant aberrantes (long terme)
        if isinstance(ltft, (int, float)):
            if abs(ltft) > 20:
                raw += 0.30  # LTFT persistant = plus grave que STFT
            elif abs(ltft) > 15:
                raw += 0.12

        # DTC actifs
        nb_dtcs = len(dtcs)
        if nb_dtcs == 1:
            raw += 0.25
        elif nb_dtcs == 2:
            raw += 0.45
        elif nb_dtcs >= 3:
            raw += 0.70

        # FIX : normalisation exponentielle → progression réaliste, pas de saturation rapide
        # 1 - e^(-x) : croissante, bornée [0, 1[, jamais exactement 1
        score = 1.0 - math.exp(-raw)

        # Niveau qualitatif (basé sur le score normalisé)
        if score < 0.10:
            niveau = "faible"
        elif score < 0.35:
            niveau = "modéré"
        elif score < 0.60:
            niveau = "élevé"
        else:
            niveau = "critique"

        return score, niveau

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_vehicle(self) -> str:
        """Retourne une chaîne lisible identifiant le véhicule."""
        parts = [
            self._vehicle_info.get("marque", ""),
            self._vehicle_info.get("modele", ""),
            self._vehicle_info.get("annee", ""),
        ]
        return " ".join(p for p in parts if p).strip() or "Inconnu"

    def update_vehicle_info(self, vehicle_info: Dict[str, str]) -> None:
        """Met à jour les informations véhicule sans recréer l'objet."""
        self._vehicle_info = vehicle_info

    def reset_history(self) -> None:
        """
        Réinitialise le buffer RPM.
        À appeler après une reconnexion OBD (évite de mélanger
        des données pré et post-reconnexion dans le calcul de stabilité).
        """
        self._rpm_history.clear()

    @staticmethod
    def compress_for_ai(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Réduit le JSON normalisé pour minimiser le coût d'inférence (LLM).
        - Garde l'essentiel : features_ia, dtcs, vehicule
        - Filtre les donnees brutes (ne garde que la valeur + unité compacte)
        - Élimine les métadonnées internes et timestamps.
        """
        if not snapshot:
            return {}

        compressed: Dict[str, Any] = {
            "vehicule": snapshot.get("vehicule", "Inconnu"),
            "features_ia": snapshot.get("features_ia", {}),
            "dtcs": snapshot.get("dtcs", []),
            "meta": {
                "mode_degrade": snapshot.get("meta", {}).get("mode_degrade", False)
            }
        }

        donnees = snapshot.get("donnees", {})
        donnees_compressees = {}
        for key, info in donnees.items():
            if isinstance(info, dict) and "label" in info and "valeur" in info:
                # Ex: {"Température moteur": "90 °C"}
                valeur_str = f"{info['valeur']} {info.get('unite', '')}".strip()
                donnees_compressees[info["label"]] = valeur_str

        if donnees_compressees:
            compressed["donnees_critiques"] = donnees_compressees

        return compressed

    @staticmethod
    def ensure_strict_schema(
        snapshot: Dict[str, Any], 
        obd_status: str, 
        meta_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Garantit un format JSON unique et prédictible (Schema Lock) pour le LLM.
        """
        features = snapshot.get("features_ia", {})
        
        meta = snapshot.get("meta", {})
        if meta_override:
            meta.update(meta_override)
            
        vehicle_state = meta.get("vehicle_state", "UNKNOWN")
        risque = features.get("score_risque", 0.0)
        niveau = features.get("indicateur_risque", "INCONNU")

        donnees = snapshot.get("donnees_critiques")
        if not donnees:
            raw_donnees = snapshot.get("donnees", {})
            donnees = {}
            for k, info in raw_donnees.items():
                if isinstance(info, dict) and "label" in info and "valeur" in info:
                    donnees[info["label"]] = f"{info['valeur']} {info.get('unite', '')}".strip()

        return {
            "status_obd": obd_status,
            "mode": vehicle_state,
            "risque": round(risque, 2) if isinstance(risque, float) else 0.0,
            "severite": niveau.upper(),
            "donnees": donnees,
            "dtcs": snapshot.get("dtcs", [])
        }
