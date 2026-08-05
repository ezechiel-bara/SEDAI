import json
import os
import sys

# Ajouter le chemin parent pour importer obd2_codes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from obd2_codes import pcodes

def enrich():
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    kb_path = os.path.join(src_dir, "knowledge_base.json")
    
    # 1. Charger la base existante
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
        print(f"Base de connaissances existante chargée : {len(kb)} codes.")
    else:
        kb = {}
        print("Aucune base existante trouvée, création d'une nouvelle.")
        
    initial_count = len(kb)
    added_count = 0
    
    # 2. Parcourir et enrichir avec pcodes
    for code, desc in pcodes.items():
        code_upper = code.upper()
        if code_upper in kb:
            # Conserver la version française / Peugeot existante ultra-qualitative
            continue
            
        desc_lower = desc.lower()
        
        # Déterminer la criticité, la priorité et l'arrêt immédiat de manière intelligente
        criticite = "MODERE"
        priority_level = 3
        requires_immediate_stop = False
        llm_allowed = True
        
        # Cas critiques : Surchauffe, Pression d'huile, Ratés d'allumage sévères, Capteurs majeurs PMH
        if any(word in desc_lower for word in ["misfire", "overheat", "pressure low", "oil pressure", "stop engine", "critical"]):
            criticite = "ELEVEE"
            priority_level = 2
        elif any(word in desc_lower for word in ["shorted", "short to ground", "short to battery", "circuit high", "open circuit", "lost communication"]):
            criticite = "MODERE"
            priority_level = 3
        elif any(word in desc_lower for word in ["efficiency", "performance", "range", "thermostat", "leak"]):
            criticite = "FAIBLE"
            priority_level = 4
            
        # Générer des symptômes personnalisés
        symptomes = ["Voyant moteur allumé"]
        if "misfire" in desc_lower:
            symptomes.extend(["Moteur qui broute", "Perte de puissance", "Vibrations anormales"])
        elif "communication" in desc_lower or "u0" in desc_lower.lower():
            symptomes.extend(["Défauts en cascade", "Affichages incohérents au tableau de bord"])
        elif "transmission" in desc_lower or "clutch" in desc_lower or "gear" in desc_lower:
            symptomes.extend(["Passage de rapports difficile", "Patinage de la boîte"])
        elif "sensor" in desc_lower or "circuit" in desc_lower:
            symptomes.extend(["Comportement moteur instable", "Consommation légèrement en hausse"])
        else:
            symptomes.append("Comportement routier altéré")
            
        # Enlever les doublons éventuels dans les symptômes
        symptomes = list(dict.fromkeys(symptomes))
        
        # Générer des recommandations intelligentes basées sur le type d'anomalie
        if "sensor" in desc_lower or "circuit" in desc_lower:
            recommandation = f"Inspecter le faisceau électrique, les connecteurs et tester le capteur associé à l'anomalie ({desc})."
        elif "communication" in desc_lower or "u0" in desc_lower.lower():
            recommandation = f"Vérifier la connectique du réseau CAN, les fusibles d'alimentation des calculateurs et l'état de charge de la batterie."
        elif "misfire" in desc_lower:
            recommandation = "Vérifier le système d'allumage (bougies, bobines) ainsi que l'injection sur le cylindre concerné."
        elif "fuel" in desc_lower or "pressure" in desc_lower:
            recommandation = "Vérifier le circuit de carburant (filtre, pompe d'alimentation, régulateur de pression) et d'éventuelles fuites."
        elif "transmission" in desc_lower or "clutch" in desc_lower or "gear" in desc_lower:
            recommandation = "Contrôler le niveau et la qualité de l'huile de boîte, ainsi que les actionneurs d'embrayage/boîte."
        else:
            recommandation = f"Faire diagnostiquer le sous-système lié à : {desc}. Vérifier les connexions physiques."

        # Ajouter à la base
        kb[code_upper] = {
            "description": desc,
            "symptomes": symptomes,
            "criticite": criticite,
            "priority_level": priority_level,
            "requires_immediate_stop": requires_immediate_stop,
            "llm_allowed": llm_allowed,
            "recommandation": recommandation
        }
        added_count += 1
        
    # 3. Sauvegarder la base de connaissances enrichie
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
        
    print(f"Enrichissement terminé avec succès !")
    print(f"Initial : {initial_count} codes | Ajoutés : {added_count} codes | Total final : {len(kb)} codes.")

if __name__ == "__main__":
    enrich()
