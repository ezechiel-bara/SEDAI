"""
diagnostic_module.py — Diagnostic IA avec Gemma3 local (SEDAI v2.0)
Gère l'analyse complète en interrogeant le modèle de langage via llama.cpp en in-process.
"""

import logging
import threading
import queue
import random
import json
import time
import re
import os
from typing import Any, Dict, List, Optional

# Logger dédié à ce module
logger = logging.getLogger("DIAGNOSTIC")


from config import (
    LLAMA_CPP_TEMPERATURE, LLAMA_CPP_N_CTX, SYSTEM_PROMPT,
    CONFIDENCE_WEIGHT_DATA, CONFIDENCE_WEIGHT_HISTORY, CONFIDENCE_WEIGHT_DTC,
    CONFIDENCE_THRESHOLD_HIGH, CONFIDENCE_THRESHOLD_MED,
    SEUIL_TEMP_MAX, SEUIL_BATT_MIN,
    PHRASES_ATTENTE_DIAG, PHRASES_ACQUITTEMENT,
    FEW_SHOT_EXAMPLES
)
from memory_module import MemoryModule
from tts_module import TTSModule
from obd_normalizer import OBDNormalizer
from ecu_state_machine import ECUStateMachine, PowerState, LogicState
from event_bus import EventBus


class DiagnosticModule(threading.Thread):
    def __init__(
        self,
        shared_state: Dict[str, Any],
        state_lock: threading.Lock,
        action_queue: queue.Queue,
        memory: MemoryModule,
        tts: TTSModule,
        event_stop: threading.Event,
        event_bus: EventBus,
        llm: Any,
    ) -> None:
        """Initialise le module de diagnostic.

        Args:
            shared_state: Dictionnaire partagé avec les données temps réel.
            state_lock: Verrou protégeant shared_state.
            action_queue: File des actions à traiter.
            memory: Module de mémoire conversationnelle.
            tts: Module de synthèse vocale.
            event_stop: Événement de demande d'arrêt.
            event_bus: Bus d'événements inter-modules.
            llm: Instance llama_cpp.Llama déjà chargée (partagée depuis main).
        """
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.state_lock = state_lock
        self.action_queue = action_queue
        self.memory = memory
        self.tts = tts
        self.event_stop = event_stop
        self.event_bus = event_bus
        self.llm = llm
        self.knowledge_base = self._load_knowledge_base()
        self.alert_cache: Dict[str, Dict[str, Any]] = {}
        self.state_machine = ECUStateMachine(event_bus=self.event_bus)
        self.event_bus.subscribe("DTC_EVENT", self.state_machine.update_logic_state)

    # Correspondance clé OBD → libellé lisible + unité
    _OBD_SCHEMA: Dict[str, Dict[str, str]] = {
        "vitesse":            {"label": "Vitesse",                    "unit": "km/h"},
        "regime":             {"label": "Régime moteur",              "unit": "RPM"},
        "temp_moteur":        {"label": "Température moteur",         "unit": "°C"},
        "maf":                {"label": "Débit air (MAF)",            "unit": "g/s"},
        "map":                {"label": "Pression admission (MAP)",   "unit": "kPa"},
        "tension":            {"label": "Tension batterie",           "unit": "V"},
        "charge":             {"label": "Charge moteur",              "unit": "%"},
        "papillon":           {"label": "Position papillon",          "unit": "%"},
        "avance":             {"label": "Avance allumage",            "unit": "°"},
        "temp_admission":     {"label": "Température admission",      "unit": "°C"},
        "pression_huile":     {"label": "Pression huile",             "unit": "kPa"},
        "pression_carburant": {"label": "Pression carburant",         "unit": "kPa"},
        "carburant":          {"label": "Niveau carburant",           "unit": "%"},
        "lambda":             {"label": "Sonde lambda (B1S1)",        "unit": "V"},
        "stft_b1":            {"label": "Correction court terme (STFT B1)", "unit": "%"},
        "ltft_b1":            {"label": "Correction long terme (LTFT B1)", "unit": "%"},
        "temp_transmission":  {"label": "Température transmission",   "unit": "°C"},
    }

    def _load_knowledge_base(self) -> Dict[str, Any]:
        kb_path = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
        if os.path.exists(kb_path):
            try:
                with open(kb_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[DIAGNOSTIC] Erreur lecture knowledge_base.json : {e}")
        return {}

    def _calculate_confidence_score(self, obd_data: Dict[str, Any], dtcs: List[str]) -> str:
        pids_presents = sum(1 for v in obd_data.values() if v is not None)
        data_score = min(pids_presents / 5.0, 1.0)
        history_score = 1.0 if self.memory.get_last_report() else 0.5
        dtc_score = 1.0
        score = ((data_score * CONFIDENCE_WEIGHT_DATA) +
                 (history_score * CONFIDENCE_WEIGHT_HISTORY) +
                 (dtc_score * CONFIDENCE_WEIGHT_DTC)) * 100
        if score >= CONFIDENCE_THRESHOLD_HIGH:
            return "ÉLEVÉ"
        elif score >= CONFIDENCE_THRESHOLD_MED:
            return "MODÉRÉ"
        else:
            return "FAIBLE"

    def _evaluate_reliability(self, obd_data: Dict[str, Any], dtcs: List[str]) -> float:
        """
        Calcule la fiabilité du diagnostic de manière déterministe (0-100).
        Basé sur la qualité des données d'entrée (capteurs présents, DTC, historique).
        """
        pids_presents = sum(1 for v in obd_data.values() if v is not None)
        data_score = min(pids_presents / 5.0, 1.0)
        history_score = 1.0 if self.memory.get_last_report() else 0.5
        dtc_score = 1.0
        
        score = ((data_score * CONFIDENCE_WEIGHT_DATA) +
                 (history_score * CONFIDENCE_WEIGHT_HISTORY) +
                 (dtc_score * CONFIDENCE_WEIGHT_DTC)) * 100
                 
        return round(score, 1)

    def _check_critical_alerts(self, obd_status: str, obd_data: Dict[str, Any], dtcs: List[str]) -> tuple[Optional[str], bool, bool]:
        current_time = time.time()
        alert_msg = None
        highest_priority = 4
        alert_id = None
        trend = "STABLE"

        all_priorities = []
        requires_stop = False

        temp = obd_data.get("temp_moteur")
        if temp is not None and temp >= SEUIL_TEMP_MAX:
            alert_id = "TEMP_CRITICAL"
            highest_priority = 1
            all_priorities.append(1)
            requires_stop = True
            alert_msg = f"Attention, surchauffe moteur détectée à {temp}°C. Arrêt immédiat et sécurisé requis pour protéger votre moteur."
        else:
            batt = obd_data.get("tension")
            if batt is not None and batt <= SEUIL_BATT_MIN:
                alert_id = "BATT_CRITICAL"
                highest_priority = 1
                all_priorities.append(1)
                alert_msg = f"Attention, tension de la batterie critique détectée à {batt} volts. Risque d'arrêt moteur imminent."

        if dtcs and self.knowledge_base:
            for d in dtcs:
                if d in self.knowledge_base:
                    info = self.knowledge_base[d]
                    p_level = info.get("priority_level", 4)
                    req_stop = info.get("requires_immediate_stop", False)
                    llm_all = info.get("llm_allowed", True)
                    
                    all_priorities.append(p_level)
                    if req_stop:
                        requires_stop = True
                        
                    if p_level == 1 or req_stop or not llm_all:
                        if p_level <= highest_priority:
                            highest_priority = p_level
                            alert_id = f"DTC_{d}"
                            criticite_val = info.get("criticite", "CRITIQUE")
                            rec = info.get("recommandation", "Arrêt recommandé.")
                            if alert_msg is None:
                                alert_msg = f"Attention, anomalie de niveau {criticite_val} détectée. Défaut {d} : {info['description']}. {rec}"

        cached = self.alert_cache.get(alert_id) if alert_id else None
        if cached:
            last_value = cached.get("value")
            if alert_id == "TEMP_CRITICAL" and temp is not None and last_value is not None:
                if temp > last_value:
                    trend = "WORSENING"
                elif temp < last_value:
                    trend = "IMPROVING"

        trend_critical = (trend == "WORSENING" and highest_priority == 1)

        # 1. Publication sur le Event Bus
        event_payload = {
            "type": "DTC_EVENT",
            "priority": highest_priority,
            "requires_stop": requires_stop,
            "trend": trend
        }
        self.event_bus.publish("DTC_EVENT", event_payload)
        
        # 2. Decision Layer (Diagnostic décide pour l'IA basé sur l'état pur)
        llm_enabled = True
        voice_alert_allowed = False
        
        if self.state_machine.power_state == PowerState.OFF:
            llm_enabled = False
        else:
            if self.state_machine.logic_state == LogicState.CRITICAL:
                llm_enabled = False
                voice_alert_allowed = True
            elif self.state_machine.logic_state == LogicState.DEGRADED:
                voice_alert_allowed = True

        if not alert_msg:
            return None, False, llm_enabled

        should_speak = voice_alert_allowed
        if cached:
            last_seen = cached["last_seen"]
            if trend == "WORSENING":
                self.alert_cache[alert_id] = {"last_seen": current_time, "value": temp if alert_id == "TEMP_CRITICAL" else None, "trend": trend}
                return alert_msg, should_speak, llm_enabled

            elapsed = current_time - last_seen
            if highest_priority == 1 and elapsed < 60:
                should_speak = False
            elif highest_priority == 2 and elapsed < 180:
                should_speak = False
            elif highest_priority > 2:
                should_speak = False

            if should_speak:
                self.alert_cache[alert_id]["last_seen"] = current_time
            return alert_msg, should_speak, llm_enabled

        self.alert_cache[alert_id] = {
            "last_seen": current_time,
            "value": temp if alert_id == "TEMP_CRITICAL" else None,
            "trend": trend
        }
        return alert_msg, should_speak, llm_enabled

    def _build_obd_json(self, obd_data: Dict[str, Any]) -> str:
        """
        Construit un JSON structuré avec valeurs décodées et unités explicites.

        Ollama reçoit uniquement :
          - des valeurs numériques décodées (jamais du HEX brut ni réponses ELM brutes)
          - l'unité physique de chaque paramètre
          - le libellé lisible en français

        Returns:
            Chaîne JSON compacte, prête à être insérée dans le prompt Ollama.
        """
        structured: Dict[str, Any] = {}
        for key, meta in self._OBD_SCHEMA.items():
            value = obd_data.get(key)
            if value is not None:
                structured[meta["label"]] = {
                    "valeur": value,
                    "unite": meta["unit"],
                }
        if not structured:
            return json.dumps({"statut": "Données OBD non disponibles"}, ensure_ascii=False)
        return json.dumps(structured, ensure_ascii=False, indent=2)

    @staticmethod
    def _get_friendly_system_name(dtc_code: str, description: str) -> str:
        """Retourne un nom de système convivial en français simple pour le LLM."""
        desc_lower = description.lower()
        code_upper = dtc_code.upper()
        
        if any(k in desc_lower for k in ["vilebrequin", "arbre à cames", "distribution", "calage", "soupape"]):
            return "distribution"
        if any(k in desc_lower for k in ["débitmètre", " air", "maf", "admission"]):
            return "admission d'air"
        if any(k in desc_lower for k in ["injecteur", "injection", "carburant", "pression essence", "pression carburant"]):
            return "injection et carburant"
        if any(k in desc_lower for k in ["raté", "allumage", "bougie", "bobine"]):
            return "allumage moteur"
        if any(k in desc_lower for k in ["refroidissement", "température moteur", "thermostat", "ventilateur"]):
            return "refroidissement moteur"
        if any(k in desc_lower for k in ["lambda", "oxygène", "o2", "catalyseur", "échappement", "fap", "egr"]):
            return "échappement et antipollution"
        if any(k in desc_lower for k in ["tension", "batterie", "alternateur", "générateur", "électrique"]):
            return "alimentation électrique"
        if any(k in desc_lower for k in ["transmission", "boîte", "embrayage", "rapport", "pont"]):
            return "transmission"
        if any(k in desc_lower for k in ["frein", "abs", "esp", "plaquette"]):
            return "freinage"
        if any(k in desc_lower for k in ["pression d'huile", "lubrification", "huile moteur"]):
            return "lubrification moteur"
        if any(k in desc_lower for k in ["suralimentation", "turbo", "compresseur"]):
            return "turbocompresseur"

        # Par plage de code standard OBD si description générique
        if code_upper.startswith("P03") or code_upper.startswith("P02"):
            return "allumage ou injection"
        if code_upper.startswith("P01"):
            return "mesure d'air ou de carburant"
        if code_upper.startswith("P04"):
            return "système antipollution"
        if code_upper.startswith("P05"):
            return "contrôle du régime ou auxiliaires"
        if code_upper.startswith("P06") or code_upper.startswith("U"):
            return "réseau électrique ou calculateur"
            
        return "gestion moteur"

    def build_prompt(
        self,
        vehicle_info: Dict[str, str],
        obd_data: Dict[str, Any],
        dtcs: List[str],
        context: str,
        ai_snapshot: Optional[Dict[str, Any]] = None,
        obd_status: str = "déconnecté",
        is_free_chat: bool = False
    ) -> List[Dict[str, str]]:
        # On n'injecte le dernier diagnostic QUE si ce n'est pas un free_chat
        # ou si le free_chat est détecté comme technique.
        context_enrichi = context
        est_technique = False
        
        if is_free_chat:
            # Détection simple : est-ce une question technique ou une conversation banale ?
            mots_techniques = [
                "moteur", "voiture", "vitesse", "température", "temp", "obd", "diagnostic",
                "défaut", "erreur", "code", "batterie", "régime", "rpm", "huile", "pression",
                "carburant", "consommation", "voyant", "alerte", "panne", "problème", "véhicule",
                "frein", "transmission", "coolant", "maf", "lambda", "capteur", "sonde"
            ]
            question_lower = context.lower()
            est_technique = any(mot in question_lower for mot in mots_techniques)
            
            # On n'injecte le dernier diagnostic que si la question est technique
            if est_technique:
                dernier = self.memory.get_last_report()
                if dernier:
                    context_enrichi = f"{context} | Dernier diagnostic : {dernier[:100]}..."
        else:
            # Pour les demandes de diagnostic explicites, on garde l'historique
            dernier = self.memory.get_last_report()
            if dernier:
                context_enrichi = f"{context} | Dernier diagnostic : {dernier[:100]}..."

        # 1. Résoudre les descriptions de tous les DTCs actifs pour l'anonymisation par système
        resolved_dtcs_info = []
        if dtcs:
            # Récupérer les descriptions dynamiques de python-obd depuis le shared_state
            dynamic_descs = {}
            if self.state_lock:
                with self.state_lock:
                    dynamic_descs = self.shared_state.get("dtc_descriptions", {})
            else:
                dynamic_descs = self.shared_state.get("dtc_descriptions", {})

            # Tenter d'importer la base de données de secours complète obd2_codes (2100+ codes)
            obd2_fallback = {}
            try:
                import sys
                import os
                sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                from obd2_codes import pcodes  # type: ignore
                obd2_fallback = pcodes
            except Exception:
                pass

            for d in dtcs:
                desc = "Anomalie générique détectée."
                if self.knowledge_base and d in self.knowledge_base:
                    desc = self.knowledge_base[d].get("description", desc)
                elif d in obd2_fallback and obd2_fallback[d]:
                    desc = obd2_fallback[d]
                elif d in dynamic_descs and dynamic_descs[d]:
                    desc = dynamic_descs[d]
                
                # Obtenir le nom de système convivial en français simple
                syst = self._get_friendly_system_name(d, desc)
                reco = "À faire inspecter par un spécialiste."
                if self.knowledge_base and d in self.knowledge_base:
                    reco = self.knowledge_base[d].get("recommandation", reco)
                
                resolved_dtcs_info.append({
                    "code": d,
                    "description": desc,
                    "systeme": syst,
                    "recommandation": reco
                })

        # Schema Lock : Format UNIQUE garanti pour le LLM, qu'on ait le snapshot IA ou non
        if ai_snapshot:
            strict_data = OBDNormalizer.ensure_strict_schema(ai_snapshot, obd_status)
            header_data = "DONNÉES ENRICHIES (SCHEMA LOCK) :"
        else:
            # Fallback déterministe simulant un snapshot à partir des données brutes
            fake_snapshot = {
                "donnees": obd_data,
                "dtcs": dtcs,
                "vehicule": f"{vehicle_info.get('marque', 'Inconnu')} {vehicle_info.get('modele', '')}",
            }
            strict_data = OBDNormalizer.ensure_strict_schema(fake_snapshot, obd_status)
            header_data = "DONNÉES BRUTES (SCHEMA LOCK - Fiabilité réduite) :"

        # Masquer les codes DTC bruts pour le LLM en remplaçant par les systèmes en défaut (naturel et sans numérotation)
        # Gestion grammaticale du préfixe ("de" ou "d'") en français selon si le nom de système commence par une voyelle
        if "dtcs" in strict_data and strict_data["dtcs"]:
            strict_data["dtcs"] = [
                "système d'" + info["systeme"] if info["systeme"][0].lower() in ['a', 'e', 'i', 'o', 'u', 'y', 'é', 'è', 'à', 'â', 'ê'] else "système de " + info["systeme"]
                for info in resolved_dtcs_info
            ]

        obd_json = json.dumps(strict_data, ensure_ascii=False, indent=2)

        if is_free_chat:
            if est_technique:
                # Question technique : on fournit les données OBD en contexte
                sys_list = [
                    "système d'" + info["systeme"] if info["systeme"][0].lower() in ['a', 'e', 'i', 'o', 'u', 'y', 'é', 'è', 'à', 'â', 'ê'] else "système de " + info["systeme"]
                    for info in resolved_dtcs_info
                ]
                user_message = f"""QUESTION DU CONDUCTEUR : "{context_enrichi}"

Contexte technique (utilise-le si pertinent) :
- État OBD : {obd_status.upper()}
- Systèmes en défaut : {', '.join(sys_list) if sys_list else 'Aucun'}
- Données moteur : {obd_json}

Réponds directement et naturellement. Tu peux faire de 2 à 4 phrases (jusqu'à 4 à 5 lignes si nécessaire) pour donner une explication cohérente et intéressante. Pas de format [ÉTAT OBD].
"""
            else:
                # Question conversationnelle simple (bonjour, merci, etc.) : pas de données OBD
                user_message = f"""QUESTION DU CONDUCTEUR : "{context_enrichi}"

Réponds directement et naturellement en 1 à 3 phrases (jusqu'à 4 lignes si nécessaire pour être chaleureux et complet). C'est une conversation simple, pas un diagnostic.
"""
        else:
            rappel = """RAPPEL :
1. Intègre l'état de connexion OBD naturellement dans votre première phrase.
2. Intègre le niveau de sévérité (CRITIQUE, MODÉRÉ, ou FAIBLE) naturellement sans jamais utiliser de crochets.
3. Reste direct, fluide et compréhensible pour le conducteur. Tu as la possibilité de faire de 2 à 4 phrases (jusqu'à 4 à 5 lignes si nécessaire) pour détailler et donner des explications intéressantes et cohérentes.
4. Si la sévérité est FAIBLE, affirme immédiatement que tout fonctionne normalement."""

            confiance_txt = self._calculate_confidence_score(obd_data, dtcs)
            kb_info = ""
            if resolved_dtcs_info:
                kb_parts = []
                for info in resolved_dtcs_info:
                    prefix = "Système d'" if info["systeme"][0].lower() in ['a', 'e', 'i', 'o', 'u', 'y', 'é', 'è', 'à', 'â', 'ê'] else "Système de "
                    kb_parts.append(
                        f"- Système concerné : {prefix}{info['systeme']}. "
                        f"Constat : {info['description']}. "
                        f"Conseil : {info['recommandation']}"
                    )
                if kb_parts:
                    kb_info = "\nINFORMATIONS TECHNIQUES SUR LES DEFAUTS (BASE DE CONNAISSANCES) :\n" + "\n".join(kb_parts) + "\n"

            user_message = f"""ENTRÉE : {obd_json}

{kb_info}
CONTEXTE : {context_enrichi}

{rappel}

EXEMPLES DE RÉFÉRENCE (FEW-SHOT) :
{FEW_SHOT_EXAMPLES}
"""
        if is_free_chat:
            custom_system_prompt = """Tu es SEDAI (Système Embarqué de Diagnostic Automobile Intelligent), un assistant vocal automobile embarqué dans le véhicule du conducteur.

IDENTITÉ ET CONCEPTEURS :
- Tu es SEDAI (Système Embarqué de Diagnostic Automobile Intelligent), un assistant de diagnostic automobile embarqué.
- Par défaut, lorsque l'on te demande de te présenter ou qui tu es, présente-toi simplement comme SEDAI, ton rôle et tes capacités de diagnostic, d'explication de pannes et de conseils mécaniques. Reste humble, accueillant et concis. Ne cite jamais le nom de tes concepteurs lors d'une simple présentation générale de toi-même.
- Tes concepteurs et créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes (avec la possibilité de préciser l'option automobile) à l'INSTI de Lokossa. Si l'utilisateur te demande explicitement qui t'a conçu ou créé, tu réponds avec cette identité précise. Sinon, ne cite jamais leurs noms de toi-même.

TES COMPÉTENCES :
- Diagnostic automobile, surveillance moteur, codes défauts (DTC)
- Explications sur le FONCTIONNEMENT des systèmes automobiles (ABS, turbo, injection, transmission, etc.)
- Conseils d'entretien et informations mécaniques générales

RÈGLES :
1. Pour les SALUTATIONS et conversations banales : réponds chaleureusement et naturellement.
2. Tu PEUX expliquer comment un système FONCTIONNE (ex: "comment fonctionne l'ABS", "c'est quoi un turbo", "à quoi sert l'huile moteur").
3. Tu NE PEUX PAS expliquer comment EFFECTUER une opération concrète (ex: "comment changer les freins", "comment démonter un pneu"). Pour ce type de demande, recommande de consulter un technicien professionnel.
4. Si on te demande qui tu es ou de te présenter : présente-toi comme SEDAI, assistant de diagnostic automobile intelligent embarqué dans le véhicule.
5. Tes compétences sont UNIQUEMENT automobiles. Tu ne fais PAS la météo, les directions, les blagues, ni d'autres sujets hors automobile.
6. Sois direct, naturel et chaleureux. Tu peux répondre en 1 à 3 phrases pour les salutations ou questions simples, mais n'hésite pas à développer jusqu'à 4 à 5 lignes (ou phrases) si la question technique, l'explication du fonctionnement d'un système ou le conseil d'entretien le nécessite pour être intéressant et complet."""
            messages: List[Dict[str, str]] = [{"role": "system", "content": custom_system_prompt.strip()}]
        else:
            messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Historique conversationnel pour la continuité contextuelle
        # Permet au LLM de comprendre les réponses de suivi (ex: "oui" après "Prêt pour la route ?")
        messages.extend(self.memory.get_history())
        messages.append({"role": "user", "content": user_message})
        return messages

    def run_gemma_analysis(self, messages: List[Dict[str, str]], is_free_chat: bool = False) -> str:
        """Exécute l'inférence via llama.cpp en in-process.

        Args:
            messages: Liste de messages au format ChatML ({role, content}).
            is_free_chat: True si conversation libre, False si diagnostic structuré.

        Returns:
            Réponse textuelle du modèle, ou message de fallback en cas d'erreur.
        """
        try:
            if is_free_chat:
                logger.info("[DIAGNOSTIC] Génération de la réponse (free chat) via llama.cpp...")
            else:
                logger.info("[DIAGNOSTIC] Génération du rapport via llama.cpp...")

            result = self.llm.create_chat_completion(
                messages=messages,
                temperature=LLAMA_CPP_TEMPERATURE,
                max_tokens=256,
            )
            ai_response: str = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            # --- LLM FAIL-SAFE (Réponse vide ou incohérente) ---
            if not ai_response:
                return "La connexion avec votre véhicule est établie. L'analyse par intelligence artificielle est momentanément limitée."

            # Si l'état est normal ou faible, on s'assure de la concision (max 2 phrases)
            is_faible = False
            for msg in messages:
                if msg["role"] == "user":
                    actual_input = msg["content"].split("EXEMPLES DE RÉFÉRENCE")[0]
                    if '"severite": "FAIBLE"' in actual_input:
                        is_faible = True
                        break

            # Nettoyage de sécurité post-inférence : supprimer les codes d'erreur bruts (ex: P0016, P0102)
            # qui auraient pu être générés par l'IA malgré les consignes strictes.
            import re
            ai_response = re.sub(r'\b[PCBU]\d{4}\b', '', ai_response)
            ai_response = re.sub(r'\s+', ' ', ai_response)
            ai_response = re.sub(r'\s+([.,!?])', r'\1', ai_response).strip()

            if is_faible:
                # On découpe par phrase pour limiter la durée de parole (sécurité électrique)
                sentences = re.split(r'(?<=[.!?]) +', ai_response)
                # On garde au maximum 3 phrases pour le niveau FAIBLE
                if len(sentences) > 3:
                    ai_response = " ".join(sentences[:3])
                    # Si on a coupé, on s'assure que le message de normalité est présent
                    if not any(word in ai_response.lower() for word in ["normal", "correct", "fonctionne"]):
                        ai_response += " Tout fonctionne normalement."

            return ai_response

        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Erreur llama.cpp : {e}")
            self.tts.speak("Une erreur d'inférence m'empêche d'établir un diagnostic.")

            # --- FAIL-SAFE DÉTERMINISTE ---
            obd_stat = str(self.shared_state.get("statut_obd", "")).lower()
            if "déconnecté" in obd_stat:
                return "Le système est actuellement déconnecté de votre véhicule. Le diagnostic est indisponible pour le moment. Veuillez vérifier la connexion matérielle de la prise O B D."
            else:
                return "La connexion avec votre véhicule est établie, mais l'analyse par intelligence artificielle est momentanément indisponible suite à une erreur d'inférence. Les données physiques restent accessibles sur votre tableau de bord."

    def run(self) -> None:
        logger.info("[DIAGNOSTIC] Démarrage du thread de diagnostic IA.")
        while not self.event_stop.is_set():
            try:
                action = self.action_queue.get(timeout=1.0)
                type_action = action.get("type")

                if type_action in ["diagnostic_request", "free_chat"]:
                    source = action.get("source", "inconnu")
                    text_context = action.get("text", "")
                    with self.state_lock:
                        obd_status   = self.shared_state.get("statut_obd", "déconnecté")
                        obd_data     = dict(self.shared_state.get("obd_data", {}))
                        dtcs         = list(self.shared_state.get("dtcs", []))
                        vehicle_info = dict(self.shared_state.get("vehicle_info", {}))
                        ai_snapshot  = self.shared_state.get("obd_snapshot_ia")

                    is_free_chat = (type_action == "free_chat")

                    # ── DÉTECTION D'INTENTION DE DIAGNOSTIC ──
                    # Si l'utilisateur demande un diagnostic via le chat textuel,
                    # on re-route la requête en diagnostic_request au lieu de free_chat.
                    INTENT_DIAGNOSTIC = [
                        "fais un diagnostic", "fais le diagnostic",
                        "faire un diagnostic", "faire le diagnostic",
                        "lance un diagnostic", "lancer un diagnostic",
                        "lance le diagnostic", "lancer le diagnostic",
                        "démarre le diagnostic", "démarrer le diagnostic",
                        "tu peux me faire le diagnostic",
                        "tu peux faire un diagnostic",
                        "peux-tu faire un diagnostic",
                        "peux tu faire un diagnostic",
                        "fais-moi un diagnostic", "fais moi un diagnostic",
                        "lance une analyse", "lancer une analyse",
                        "fais une analyse", "faire une analyse",
                        "analyse le véhicule", "analyser le véhicule",
                        "état du véhicule", "état de la voiture",
                        "vérifie le moteur", "vérifier le moteur",
                        "fais un bilan", "faire un bilan",
                        "est-ce que tu peux me faire le diagnostic",
                        "est ce que tu peux me faire le diagnostic",
                        "est-ce que tu peux faire un diagnostic",
                        "diagnostique",
                        "lis l'obd", "lire l'obd", "diagnostic obd", 
                        "lis l'obédée", "lire l'obédée", "diagnostic obédée",
                        "lis l'au b d", "lire l'au b d", "lis obd deux",
                        "lire obd deux", "lis l'obédée deux"
                    ]

                    if is_free_chat:
                        question_norm_intent = text_context.strip().lower().rstrip("!?., ")
                        # Vérifier si c'est une intention de diagnostic
                        intent_match = any(intent in question_norm_intent for intent in INTENT_DIAGNOSTIC)
                        if intent_match:
                            logger.info(f"[DIAGNOSTIC] Intention de diagnostic détectée dans le chat : '{text_context}' → re-routage en diagnostic_request.")
                            is_free_chat = False
                            type_action = "diagnostic_request"
                            # Conserver la question de l'utilisateur intacte pour une meilleure cohérence

                    # ── RÉPONSES RAPIDES (bypass LLM pour les messages simples) ──
                    # Gemma3 est trop biaisé pour répondre naturellement aux salutations.
                    # Pour ces cas précis, on retourne une réponse variée sans LLM.
                    REPONSES_RAPIDES = {
                        # Salutations
                        "bonjour": [
                            "Bonjour ! Heureux de vous retrouver.",
                            "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
                            "Bonjour ! Prêt pour la route ?",
                            "Bonjour ! Je suis à votre service.",
                            "Bonjour ! Ravi de vous revoir.",
                        ],
                        "salut": [
                            "Salut ! Comment allez-vous ?",
                            "Salut ! Quoi de neuf aujourd'hui ?",
                            "Salut ! Prêt à prendre la route ?",
                            "Salut ! Je suis à votre écoute.",
                            "Salut ! Ravi de vous voir.",
                        ],
                        "hello": [
                            "Hello ! Ravi de vous parler.",
                            "Hello ! Comment puis-je vous aider ?",
                            "Hello ! Bienvenue à bord.",
                        ],
                        "bonsoir": [
                            "Bonsoir ! J'espère que votre journée s'est bien passée.",
                            "Bonsoir ! Comment puis-je vous aider ce soir ?",
                            "Bonsoir ! Bonne route ce soir.",
                        ],
                        "hey": [
                            "Hey ! Que puis-je faire pour vous ?",
                            "Hey ! Je suis prêt à vous aider.",
                            "Hey ! À votre service.",
                        ],
                        "coucou": [
                            "Coucou ! Je suis là pour vous.",
                            "Coucou ! Comment allez-vous ?",
                            "Coucou ! Prêt pour un diagnostic ?",
                        ],
                        # Remerciements
                        "merci": [
                            "De rien ! C'est un plaisir de vous aider.",
                            "Avec plaisir ! N'hésitez pas.",
                            "Je vous en prie !",
                            "De rien ! Je suis là pour ça.",
                        ],
                        "merci beaucoup": [
                            "Avec grand plaisir !",
                            "C'est tout naturel !",
                            "Ravi d'avoir pu vous aider !",
                        ],
                        "super merci": ["Avec plaisir !", "Content de vous avoir aidé !"],
                        "d'accord merci": [
                            "Je vous en prie ! N'hésitez pas si vous avez besoin d'autre chose.",
                            "Avec plaisir ! Je reste disponible.",
                        ],
                        "ok merci": ["Avec plaisir !", "De rien !"],
                        # Présentation / Identité
                        "présente toi": [
                            "Je suis SEDAI, votre assistant de diagnostic automobile intelligent. Je surveille votre véhicule en temps réel et je peux analyser son état mécanique.",
                            "Je m'appelle SEDAI ! Je suis un système embarqué de diagnostic automobile. Je peux analyser votre moteur, détecter les pannes et vous informer sur l'état de votre véhicule.",
                        ],
                        "peux tu te présenter": [
                            "Bien sûr ! Je suis SEDAI, un assistant de diagnostic automobile intelligent embarqué dans votre véhicule. Je peux surveiller le moteur, détecter les anomalies et vous expliquer l'état de votre voiture.",
                        ],
                        "peux-tu te présenter": [
                            "Bien sûr ! Je suis SEDAI, un assistant de diagnostic automobile intelligent embarqué dans votre véhicule. Je surveille le moteur, détecte les anomalies et vous tiens informé.",
                        ],
                        "bonjour peux tu te présenter": [
                            "Bonjour ! Je suis SEDAI, votre assistant de diagnostic automobile. Je surveille votre véhicule en temps réel, je détecte les pannes et je vous aide à comprendre l'état de votre moteur.",
                        ],
                        "bonjour peux-tu te présenter": [
                            "Bonjour ! Je suis SEDAI, votre assistant de diagnostic automobile intelligent. Je peux analyser votre moteur, détecter les codes défauts et vous informer sur l'état de votre véhicule.",
                        ],
                        "c'est quoi ton nom": [
                            "Je m'appelle SEDAI, enchanté ! Je suis votre assistant de diagnostic automobile.",
                            "Mon nom est SEDAI ! Système Embarqué de Diagnostic Automobile Intelligent.",
                        ],
                        "c'est quoi déjà ton nom": [
                            "Je m'appelle SEDAI ! Système Embarqué de Diagnostic Automobile Intelligent.",
                            "SEDAI ! Je suis toujours là pour vous.",
                        ],
                        "tu es quoi": [
                            "Je suis SEDAI, un assistant de diagnostic automobile intelligent embarqué dans votre véhicule.",
                            "SEDAI, votre assistant automobile ! Je surveille le moteur et détecte les anomalies.",
                        ],
                        "c'est quoi sedai": [
                            "SEDAI signifie Système Embarqué de Diagnostic Automobile Intelligent. Je suis un assistant embarqué qui surveille votre véhicule en temps réel.",
                            "SEDAI, c'est votre assistant automobile intelligent ! Je peux diagnostiquer votre véhicule, détecter les pannes et vous informer sur l'état mécanique.",
                        ],
                        "que fais-tu": [
                            "Je surveille votre véhicule en temps réel, je détecte les anomalies et je peux faire des diagnostics complets du moteur.",
                            "Je suis spécialisé dans le diagnostic automobile. Je lis les données de votre moteur et je vous alerte en cas de problème.",
                        ],
                        "que fais tu": [
                            "Je surveille votre véhicule en temps réel et je peux analyser l'état de votre moteur à tout moment.",
                            "Je fais du diagnostic automobile ! Je lis les capteurs du moteur et je détecte les pannes.",
                        ],
                        "comment tu peux m'aider": [
                            "Je peux diagnostiquer votre véhicule, surveiller le moteur en temps réel, détecter les codes défauts et vous expliquer l'état mécanique de votre voiture.",
                        ],
                        "comment peux-tu m'aider": [
                            "Je peux analyser votre moteur, détecter les pannes, lire les codes défauts et vous informer sur l'état de votre véhicule en temps réel.",
                        ],
                        "quelles questions je peux te poser": [
                            "Vous pouvez me demander un diagnostic, l'état du moteur, les codes défauts, ou toute question sur votre véhicule et la mécanique automobile !",
                        ],
                        "quel sont les genres de questions que je peux te poser": [
                            "Vous pouvez me poser des questions sur le diagnostic de votre véhicule, l'état du moteur, les codes d'erreur, ou encore sur le fonctionnement de composants automobiles comme l'ABS, le turbo, la transmission, etc.",
                        ],
                        # Politesse
                        "ça va": [
                            "Très bien, merci ! Et vous, comment allez-vous ?",
                            "Ça roule ! Et vous ?",
                            "Au top ! Prêt à vous aider.",
                        ],
                        "ca va": [
                            "Très bien, merci ! Et vous ?",
                            "Ça roule ! Comment puis-je vous aider ?",
                        ],
                        "comment ça va": [
                            "Très bien, merci ! J'espère que tout va bien pour vous.",
                            "Ça va bien ! Et vous, comment allez-vous ?",
                            "Au top, merci ! Prêt à prendre la route avec vous.",
                        ],
                        "au revoir": [
                            "Au revoir ! Bonne route.",
                            "Au revoir ! À bientôt.",
                            "Au revoir ! Conduisez prudemment.",
                        ],
                        "à bientôt": [
                            "À bientôt ! N'hésitez pas si vous avez besoin de moi.",
                            "À bientôt ! Bonne route.",
                        ],
                        "ok": ["D'accord !", "Compris !", "Très bien !"],
                        "d'accord": ["Parfait !", "Très bien !", "Entendu !"],
                        "qui es-tu": ["Je suis SEDAI, votre assistant de diagnostic automobile intelligent ! Je suis conçu pour vous aider à comprendre votre véhicule, diagnostiquer les anomalies et vous donner des conseils d'entretien."],
                        "qui es tu": ["Je suis SEDAI, votre assistant de diagnostic automobile intelligent ! Je suis conçu pour vous aider à comprendre votre véhicule, diagnostiquer les anomalies et vous donner des conseils d'entretien."],
                        "qui t'a créé": ["J'ai été conçu et développé par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en 3ème année de Licence Professionnelle en Maintenance des Systèmes option Automobile à l'INSTI de Lokossa."],
                        "qui t'a cree": ["J'ai été conçu et développé par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en 3ème année de Licence Professionnelle en Maintenance des Systèmes option Automobile à l'INSTI de Lokossa."],
                        "qui sont tes créateurs": ["Mes créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel, étudiants de l'INSTI de Lokossa en option automobile !"],
                        "qui sont tes createurs": ["Mes créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel, de l'INSTI de Lokossa."],
                        "qui t'a fabriqué": ["J'ai été fièrement développé par BARA Ezechiel Merveil et BOGNINOU Armel à l'INSTI de Lokossa."],
                        "qui t'a fabrique": ["J'ai été développé par BARA Ezechiel Merveil et BOGNINOU Armel à l'INSTI de Lokossa."],
                        "qui est ton créateur": ["Mes créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel de l'INSTI de Lokossa."],
                        "qui est ton createur": ["Mes créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel, étudiants à l'INSTI de Lokossa."],
                        "qui a développé le système": ["Ce système a été développé par BARA Ezechiel Merveil et BOGNINOU Armel, à l'INSTI de Lokossa."],
                        "qui a developpe le systeme": ["Ce système a été développé par BARA Ezechiel Merveil et BOGNINOU Armel de l'INSTI de Lokossa."],
                        "qui est à la base du développement": ["Le développement de ce système a été assuré par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes à l'INSTI de Lokossa."],
                        "qui est a la base du developpement": ["Le développement de ce système a été assuré par BARA Ezechiel Merveil et BOGNINOU Armel de l'INSTI de Lokossa."],
                        "par qui as-tu été conçu": ["J'ai été conçu par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants à l'INSTI de Lokossa."],
                        "par qui as-tu ete concu": ["J'ai été conçu par BARA Ezechiel Merveil et BOGNINOU Armel à l'INSTI de Lokossa."],
                        "par qui as tu été conçu": ["J'ai été conçu par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants de l'INSTI de Lokossa."],
                        "c'est qui tes concepteurs": ["Mes concepteurs sont BARA Ezechiel Merveil et BOGNINOU Armel de l'INSTI de Lokossa."],
                        "c'est qui tes createurs": ["Mes créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel de l'INSTI de Lokossa."],
                        "qui sont bara et bogninou": ["Ezechiel Merveil BARA et Armel BOGNINOU sont les deux étudiants en Maintenance Automobile à l'INSTI de Lokossa qui m'ont entièrement conçu et développé !"],
                        "qui est bara": ["BARA Ezechiel Merveil est l'un de mes deux créateurs, étudiant à l'INSTI de Lokossa."],
                        "qui est bogninou": ["BOGNINOU Armel est l'un de mes deux ingénieux créateurs, étudiant à l'INSTI de Lokossa."],
                        "c'est quoi l'insti": ["L'INSTI est l'Institut National Supérieur de Technologie Industrielle situé à Lokossa. C'est l'établissement prestigieux d'où viennent mes créateurs."],
                        "c'est quoi insti": ["L'INSTI est l'Institut National Supérieur de Technologie Industrielle de Lokossa, où étudient mes concepteurs."],
                        "où as tu été créé": ["J'ai été créé à l'INSTI de Lokossa par Ezechiel Merveil BARA et Armel BOGNINOU."],
                        "ou as tu ete cree": ["J'ai été créé à l'INSTI de Lokossa par Ezechiel Merveil BARA et Armel BOGNINOU."],
                        "qui t'a programmé": ["J'ai été programmé par Ezechiel Merveil BARA et Armel BOGNINOU à l'INSTI de Lokossa."],
                        "qui t'a programme": ["J'ai été programmé par Ezechiel Merveil BARA et Armel BOGNINOU à l'INSTI de Lokossa."],
                        "d'où viens tu": ["Je viens de l'INSTI de Lokossa, conçu par Ezechiel Merveil BARA et Armel BOGNINOU."],
                        "d'ou viens tu": ["Je viens de l'INSTI de Lokossa, conçu par Ezechiel Merveil BARA et Armel BOGNINOU."],
                        "tu viens d'où": ["Je viens de l'INSTI de Lokossa, où j'ai été développé par Ezechiel Merveil BARA et Armel BOGNINOU."],
                        "tu viens d'ou": ["Je viens de l'INSTI de Lokossa, conçu par Ezechiel Merveil BARA et Armel BOGNINOU."],

                    }

                    if is_free_chat:
                        question_norm = text_context.strip().lower().rstrip("!?., ")
                        
                        # ── ROUTAGE INTELLIGENT (Bypass LLM pour les salutations, présentation et créateurs) ──
                        reponse_directe = None
                        
                        # A. Mots-clés de création / concepteurs / développeurs
                        keywords_concepteurs = ["crée", "cree", "conçu", "concu", "créateur", "createur", 
                                                "développe", "developpe", "concepteur", "fabrique", "fabriqué", 
                                                "programme", "programmé", "bara", "bogninou", "insti", "lokossa"]
                        
                        # B. Mots-clés de présentation
                        keywords_presentation = ["présente", "presente", "qui es-tu", "qui es tu", "ton nom", 
                                                 "t'appelles", "tu es quoi", "c'est quoi sedai", "que fais-tu", 
                                                 "que fais tu", "comment tu peux m'aider", "comment peux-tu m'aider",
                                                 "quelles questions", "quels genres de questions", "tu es qui"]

                        if any(kw in question_norm for kw in keywords_concepteurs):
                            # Liste consolidée de réponses sur les créateurs
                            reponses_createurs = [
                                "J'ai été conçu et développé par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Licence Professionnelle de Maintenance des Systèmes (option automobile) à l'INSTI de Lokossa.",
                                "Mes concepteurs sont BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes (option automobile) à l'INSTI de Lokossa !",
                                "Ce système a été fièrement développé par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes à l'INSTI de Lokossa.",
                                "Le développement de ce système embarqué intelligent a été assuré par BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes (option automobile) de l'INSTI de Lokossa."
                            ]
                            reponse_directe = random.choice(reponses_createurs)
                            logger.info("[DIAGNOSTIC] Bypass LLM intelligent : question concepteurs détectée → réponse explicite.")

                        elif any(kw in question_norm for kw in keywords_presentation):
                            # Liste consolidée de présentations de SEDAI (humble et sans noms propres)
                            reponses_presentation = [
                                "Je suis SEDAI, votre assistant de diagnostic automobile intelligent ! Je suis conçu pour vous aider à comprendre votre véhicule, diagnostiquer les anomalies et vous donner des conseils d'entretien.",
                                "Je m'appelle SEDAI ! Je suis un système embarqué de diagnostic automobile. Je peux analyser votre moteur, détecter les pannes et vous informer sur l'état de votre véhicule.",
                                "Je suis SEDAI, votre assistant de diagnostic automobile intelligent. Je surveille votre véhicule en temps réel et je peux analyser son état mécanique.",
                                "SEDAI signifie Système Embarqué de Diagnostic Automobile Intelligent. Je suis un assistant embarqué qui surveille votre véhicule en temps réel."
                            ]
                            reponse_directe = random.choice(reponses_presentation)
                            logger.info("[DIAGNOSTIC] Bypass LLM intelligent : question de présentation détectée → présentation simple.")

                        else:
                            # C. Vérification de correspondance exacte dans le dictionnaire standard (salutations, remerciements, etc.)
                            reponses = REPONSES_RAPIDES.get(question_norm)
                            if reponses:
                                reponse_directe = random.choice(reponses)
                                logger.info(f"[DIAGNOSTIC] Réponse rapide (bypass LLM) exacte pour : '{text_context}'")

                        if reponse_directe:
                            report = reponse_directe
                            # Sauvegarder en mémoire pour la cohérence conversationnelle
                            self.memory.add_exchange("user", text_context, "assistant", report)
                            with self.state_lock:
                                self.shared_state["dernier_chat"] = {"texte": report, "source": source, "timestamp": time.time()}
                            self.tts.speak(report)
                            continue  # Passe à la prochaine action sans appeler le LLM

                    # ── VÉRIFICATION DES ALERTES CRITIQUES (BYPASS LLM VIA STATE MACHINE) ──
                    critical_alert, should_speak, llm_enabled = self._check_critical_alerts(obd_status, obd_data, dtcs)
                    
                    if not llm_enabled:
                        msg = critical_alert or "[ALERTE] Mode critique actif. Assistance vocale IA suspendue pour raison de sécurité."
                        logger.warning(f"[DIAGNOSTIC] LLM désactivé par la State Machine.")
                        if is_free_chat or critical_alert:
                            if should_speak:
                                self.tts.speak(msg)
                            with self.state_lock:
                                if type_action == "diagnostic_request" and critical_alert:
                                    self.shared_state["dernier_rapport"] = {"texte": critical_alert, "source": source}
                                elif type_action == "free_chat":
                                    self.shared_state["dernier_chat"] = {"texte": msg, "source": source, "timestamp": time.time()}
                        self.action_queue.task_done()
                        continue

                    # Phrase d'attente vocale avant de bloquer sur l'inférence
                    if type_action == "diagnostic_request":
                        phrase_attente = random.choice(PHRASES_ATTENTE_DIAG)
                        self.tts.speak(phrase_attente)
                        # CRITIQUE: Attendre que le TTS finisse de parler avant de lancer llama.cpp
                        # Sinon, llama.cpp prend 100% du CPU et Piper n'arrive pas à synthétiser la voix.
                        self.tts.message_queue.join()

                    messages = self.build_prompt(
                        vehicle_info, obd_data, dtcs,
                        context=text_context,
                        ai_snapshot=ai_snapshot,
                        obd_status=obd_status,
                        is_free_chat=is_free_chat
                    )
                    report = self.run_gemma_analysis(messages, is_free_chat=is_free_chat)
                    
                    # --- ÉVALUATION DE FIABILITÉ (Déterministe) ---
                    reliability_score = 100.0
                    if type_action == "diagnostic_request" and not is_free_chat:
                         reliability_score = self._evaluate_reliability(obd_data, dtcs)
                         logger.info(f"[DIAGNOSTIC] Fiabilité calculée : {reliability_score}%")

                    self.memory.add_exchange("user", text_context, "assistant", report)
                    
                    if type_action == "diagnostic_request":
                        with self.state_lock:
                            self.shared_state["dernier_rapport"] = {
                                "texte": report, 
                                "source": source,
                                "fiabilite": reliability_score
                            }
                            # Stocker séparément pour un accès direct WS
                            self.shared_state["reliability_score"] = reliability_score
                    elif type_action == "free_chat":
                        with self.state_lock:
                            self.shared_state["dernier_chat"] = {"texte": report, "source": source, "timestamp": time.time()}
                    
                    if type_action == "diagnostic_request" and not is_free_chat:
                        report_vocal = f"{report} Ce diagnostic est estimé fiable à {int(reliability_score)}%."
                        self.tts.speak(report_vocal)
                    else:
                        self.tts.speak(report)

                elif type_action == "get_dtcs":
                    with self.state_lock:
                        dtcs = list(self.shared_state.get("dtcs", []))
                    if dtcs:
                        self.tts.speak(f"J'ai détecté les défauts suivants : {', '.join(dtcs)}.")
                    else:
                        self.tts.speak("Aucun code défaut détecté.")

                elif type_action == "clear_dtcs":
                    acquittement = random.choice(PHRASES_ACQUITTEMENT)
                    self.tts.speak(f"{acquittement} Je demande l'effacement des codes défauts.")

                elif type_action == "speak":
                    texte = action.get("text", "")
                    if texte:
                        self.tts.speak(texte)

                elif type_action == "repeat_last":
                    with self.state_lock:
                        dernier = self.shared_state.get("dernier_rapport", {})
                        texte = dernier.get("texte", "") if dernier else ""
                    if texte:
                        self.tts.speak(texte)
                    else:
                        self.tts.speak("Je n'ai pas de message récent à répéter.")

                elif type_action == "transcription":
                    with self.state_lock:
                        self.shared_state["derniere_transcription"] = action.get("text", "")

                self.action_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[DIAGNOSTIC] Erreur inattendue : {e}")
        logger.info("[DIAGNOSTIC] Arrêt du thread de diagnostic.")
