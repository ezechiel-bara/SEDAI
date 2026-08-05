import os

# ============================================================
# config.py — Constantes globales du système SEDAI v2.0
# Modifier ce fichier pour reconfigurer le système.
# NE JAMAIS modifier depuis d'autres fichiers.
# ============================================================

# --- CHEMINS DYNAMIQUES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- LLAMA.CPP ---
HF_REPO_ID = "bartowski/google_gemma-3-4b-it-GGUF"        # Dépôt HuggingFace — Gemma 3 (génération 3, 4B paramètres)
HF_FILENAME = "google_gemma-3-4b-it-Q5_K_M.gguf"         # Quantification Q4_K_M : meilleur ratio qualité/RAM pour Pi 5
LLAMA_CPP_MODEL_PATH = os.path.join(BASE_DIR, "models", HF_FILENAME) # Chemin local vers le modèle GGUF
LLAMA_CPP_N_GPU_LAYERS = 0     # CPU uniquement (Pi 5 n'a pas de GPU dédié)
LLAMA_CPP_N_CTX        = 4096  # 4096 tokens pour une robustesse maximale en conditions réelles (multi-pannes)
LLAMA_CPP_N_BATCH      = 512   # Augmenté à 512 pour un traitement plus rapide du prompt sur Pi 5 8 Go
LLAMA_CPP_N_THREADS    = 4     # 4 cœurs sur Pi 5 (laisse 4 cœurs libres pour le reste du système)
LLAMA_CPP_VERBOSE      = False # Afficher les logs détaillés de llama.cpp
LLAMA_CPP_TEMPERATURE  = 0.4   # Fortement réduit pour un output ultra-déterministe et répétable (optimisation benchmark)
LLAMA_CPP_TOP_P        = 0.9   # Top P sampling
LLAMA_CPP_TIMEOUT      = 300   # secondes — le 4B peut prendre jusqu'à 5 min à charger sur Pi 5


# --- OBD-II ---
OBD_PORT            = "/dev/ttyUSB0"
OBD_BAUDRATE        = 38400 # Vitesse standard stable
OBD_TIMEOUT         = 15    # Augmenté pour laisser le temps aux clones de répondre
OBD_RECONNECT_DELAY = 15   # secondes (legacy, remplacé par backoff)
OBD_PROTOCOL        = "auto" # "auto" pour détection automatique intelligente (séquentiel en fallback)
OBD_CHECK_VOLTAGE   = False # Clone ELM327 v1.5 : AT RV retourne 'OK' au lieu de la tension

# --- OBD-II SÉCURITÉ (ANTI-SURCHARGE ELM327) ---
# Délai minimum entre deux requêtes PID consécutives.
# Indispensable pour les ELM327 clones (UART lent, buffer fragile).
OBD_INTER_PID_DELAY   = 0.30   # secondes — 300 ms entre chaque PID (sécurité accrue pour clones)

# --- SÉCURITÉ VÉHICULE (SÉCURITÉ MOTEUR & CAN) ---
OBD_STABILIZATION_DELAY = 10.0   # secondes — temps moteur stable avant actions critiques (Mode 04)
OBD_IDLE_RPM_THRESHOLD  = 800    # RPM — régime considéré "idle safe"

# Nombre d'erreurs consécutives d'un même PID avant de le désactiver.
OBD_PID_ERROR_THRESHOLD = 3

# Nombre d'erreurs de communication globales avant de forcer une reconnexion.
OBD_GLOBAL_ERROR_THRESHOLD = 5

# --- OBD-II RECONNEXION BACKOFF EXPONENTIEL ---
# Évite de saturer le port série avec des tentatives de reconnexion répétées.
OBD_BACKOFF_BASE    = 3.0    # secondes — délai initial (réduit pour réactivité)
OBD_BACKOFF_FACTOR  = 2.0    # multiplicateur exponentiel
OBD_BACKOFF_MAX     = 120.0  # secondes — plafond backoff

# --- OBD-II PORTS FALLBACK (SCAN MULTI-PORTS) ---
# Liste optimisée pour éviter les scans trop longs sur Raspberry Pi.
OBD_FALLBACK_PORTS = [
    "/dev/ttyACM0", # Port USB standard pour ELM327 USB (Arduino/CDC)
    "/dev/ttyUSB1",
]

# --- OBD-II TIME-SLICING CYCLES ---
# Définit la fréquence relative de chaque groupe de PIDs.
# Le cycle critique tourne à ~1 Hz, les autres sont lus moins souvent.
OBD_CYCLE_CRITICAL_INTERVAL  = 1.5   # secondes — RPM, TEMP, VOLTAGE
OBD_CYCLE_STANDARD_EVERY     = 3     # toutes les N itérations critiques
OBD_CYCLE_SECONDARY_EVERY    = 8     # toutes les N itérations critiques
OBD_CYCLE_OPTIONAL_EVERY     = 30    # toutes les N itérations critiques
OBD_CAN_BUDGET_MS            = 4000  # latence max par cycle (ms)

# --- SÉCURITÉ DEGRADED MODE ---
OBD_DEGRADED_MODE_INTERVAL = 3.0     # secondes — rythme ralenti en mode dégradé
DEGRADED_VOLTAGE_THRESHOLD = 11.5    # V — Seuil d'activation (doit être cohérent avec SEUIL_BATT_MIN)
DEGRADED_VOLTAGE_RECOVERY_THRESHOLD = 12.0 # V — seuil de rétablissement (hystérésis)
DEGRADED_RECOVERY_CYCLES = 5         # nb de cycles > 12V requis pour rétablir le mode normal

# --- OBD-II WATCHDOG ELM327 ---
# Si aucune réponse valide n'est reçue pendant cette durée → reset connexion.
OBD_WATCHDOG_TIMEOUT = 45.0  # secondes

# --- WEBSOCKET ---
WS_HOST          = "0.0.0.0"
WS_PORT          = 8765
WS_SEND_INTERVAL = 1  # secondes entre chaque envoi de données
WS_PING_INTERVAL = None # Désactivé pour éviter les exceptions de keepalive ping en cas de déconnexion
WS_PING_TIMEOUT  = None

# --- SURVEILLANCE ---
MONITOR_INTERVAL = 30  # secondes entre chaque vérification

# --- SEUILS D'ANOMALIE STANDARDS ---
SEUIL_TEMP_MAX    = 100  # °C  — température moteur critique
SEUIL_RPM_MAX     = 6500  # RPM — régime moteur critique
SEUIL_RPM_DUREE   = 10    # secondes — durée avant alerte RPM
SEUIL_CHARGE_MAX  = 95    # %   — charge moteur critique
SEUIL_CHARGE_DUREE = 20   # secondes — durée avant alerte charge
SEUIL_BATT_MIN    = 11.5  # V   — tension batterie minimale (cohérent avec DEGRADED_VOLTAGE_THRESHOLD)
SEUIL_BATT_MAX    = 15.5  # V   — tension batterie maximale
SEUIL_CARBURANT   = 10    # %   — niveau carburant critique

# --- SEUILS D'ANOMALIE ÉTENDUS ---
SEUIL_TEMP_TRANSMISSION_MAX = 120  # °C — température transmission critique
SEUIL_FUEL_TRIM_DEVIATION   = 20   # %  — déviation STFT/LTFT avant alerte
SEUIL_MISFIRE_COUNT         = 50   # nombre de ratés par cylindre avant alerte (Phase 2)

# --- PRIORITÉ DES PIDs (Time-Slicing) ---
# Cycle CRITIQUE : lu à chaque itération (~1 Hz)
# Max 3 PIDs — uniquement les paramètres vitaux.
OBD_PIDS_CRITIQUES = [
    "RPM", "COOLANT_TEMP", "CONTROL_MODULE_VOLTAGE"
]
# Cycle STANDARD : lu toutes les OBD_CYCLE_STANDARD_EVERY itérations
# Max 6 PIDs — paramètres de performance et carburant.
OBD_PIDS_STANDARD = [
    "SPEED", "ENGINE_LOAD", "MAF",
    "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "FUEL_LEVEL"
]
# Cycle SECONDAIRE : lu toutes les OBD_CYCLE_SECONDARY_EVERY itérations
# PIDs d'information complémentaire.
OBD_PIDS_SECONDAIRES = [
    "THROTTLE_POS", "INTAKE_TEMP", "O2_B1S1"
]
# Cycle OPTIONNEL : lu toutes les OBD_CYCLE_OPTIONAL_EVERY itérations
# PIDs à disponibilité variable selon constructeur — jamais critiques.
OBD_PIDS_OPTIONNELS = [
    "INTAKE_PRESSURE", "FUEL_PRESSURE", "TIMING_ADVANCE", "OIL_TEMP"
]

# --- SCORE DE CONFIANCE (RULE ENGINE) ---
CONFIDENCE_WEIGHT_DATA    = 0.4  # Poids de la qualité des données (PIDs reçus)
CONFIDENCE_WEIGHT_HISTORY = 0.3  # Poids de la cohérence avec l'historique
CONFIDENCE_WEIGHT_DTC     = 0.3  # Poids des DTC (1.0 si DTC = aucun ou expliqués par PIDs)
CONFIDENCE_THRESHOLD_HIGH = 80   # Seuil pour "ÉLEVÉE"
CONFIDENCE_THRESHOLD_MED  = 50   # Seuil pour "MODÉRÉE"

# --- BENCHMARK FUZZY LOGIC ---
BENCHMARK_WEIGHT_MOTS_CLES   = 0.98   # Poids de la correspondance des mots-clés (98%) - Priorité technique
BENCHMARK_WEIGHT_SIMILITUDE  = 0.02   # Poids de la similarité globale de phrase (2%) - Baisse de l'exigence syntaxique
BENCHMARK_SEUIL_REUSSITE     = 0.65  # Score minimum pour valider un diagnostic
BENCHMARK_PENALITE_SEVERITE  = 0.33  # Pénalité si la sévérité est incorrecte

# --- MÉMOIRE CONVERSATIONNELLE ---
MEMORY_MAX_EXCHANGES = 2  # Réduit de 4 à 2 pour accélérer l'inférence du modèle 4b
MEMORY_FILE_PATH     = os.path.join(BASE_DIR, "conversation_history.json")

# --- PIPER TTS ---
PIPER_MODEL      = "fr_FR-siwis-medium.onnx"
PIPER_MODEL_JSON = "fr_FR-siwis-medium.onnx.json"
PIPER_MODEL_PATH = os.path.join(BASE_DIR, "models", "piper")
DEFAULT_AUDIO_VOLUME = 85

# --- VOSK ASR ---
VOSK_MODEL_PATH    = os.path.join(BASE_DIR, "models", "vosk", "vosk-model-fr-0.6-linto-2.2.0")
VOSK_SAMPLE_RATE   = 16000   # Taux attendu par le moteur Vosk
AUDIO_CAPTURE_RATE = 48000   # Taux de capture audio (48000 Hz standard USB, décimé à 16kHz pour Vosk)
AUDIO_AUTO_DETECT  = True    # Détection dynamique du micro USB (évite les crashs si l'index change)

AUDIO_INPUT_DEVICE = None    # Index par défaut (utilisé si AUTO_DETECT échoue, None utilise le micro par défaut)
AUDIO_OUTPUT_DEVICE = "plughw:CARD=UACDemoV10,DEV=0" # Périphérique de sortie audio pour aplay
AUDIO_CHANNELS     = 1       # Nombre de canaux (Mono)

# --- COMMANDES VOCALES ---
VOICE_CMD_DIAGNOSE = ["fais un diagnostic", "lance un diagnostic", "démarre le diagnostic", "analyse le véhicule", "fais une analyse", "fais un bilan", "état général", "vérifie le moteur", "lis l'obd", "lire l'obd", "diagnostic obd", "lis l'obédée", "lire l'obédée", "diagnostic obédée", "lis l'au b d", "lire l'au b d", "lis obd deux", "lire obd deux", "lis l'obédée deux"]
VOICE_CMD_STATUS   = ["quel est l'état", "état du véhicule", "comment va la voiture", "comment va le moteur", "état du moteur", "donne moi l'état", "état de l'obd", "état de l'obédée", "état de l'au b d"]
VOICE_CMD_DTCS     = ["quels sont les défauts", "quels sont les codes défauts", "lire les défauts", "lire le code erreur", "lire les codes erreurs", "y a-t-il des erreurs", "vérifier les erreurs", "y a-t-il des défauts", "donne les codes obd", "donne les codes obédée", "lire défauts obd", "lire défauts obédée"]
VOICE_CMD_CLEAR    = ["efface les défauts", "effacer les défauts", "efface les erreurs", "effacer les erreurs", "supprime les défauts", "efface défauts obd", "efface défauts obédée"]
VOICE_CMD_REPEAT   = ["répète", "répéter", "redis", "tu peux répéter"]

# --- PHRASES D'UX VOCALE (Aléatoires) ---
PHRASES_ATTENTE_DIAG = [
    "Acquisition des données terminée. L'intelligence artificielle analyse actuellement les paramètres du moteur. Merci de patienter quelques instants.",
    "J'ai bien reçu votre demande. Je lance l'analyse approfondie des systèmes. Cela peut prendre environ une minute.",
    "C'est noté. Je compile les données de diagnostic et je lance l'analyse. Veuillez patienter.",
    "Analyse en cours. Je vérifie les capteurs et l'état du moteur. Merci de patienter un instant."
]

PHRASES_ACQUITTEMENT = [
    "Commande reçue.",
    "C'est noté.",
    "Je m'en occupe.",
    "Entendu.",
    "Très bien."
]

PHRASES_DEMARRAGE = [
    "Initialisation terminée. Système embarqué opérationnel.",
    "Salut! Système SEDAI démarré et prêt pour le diagnostic.",
    "SEDAI activé. Prêt à surveiller votre véhicule.",
    "Salut. Connexion système établie, je suis à votre écoute.",
    "Lancement réussi. Le diagnostic intelligent est opérationnel.",
    "Salut! Système opérationnel, prêt pour l'analyse du moteur."
]


# --- LOGGING ---
LOG_FILE_PATH    = os.path.join(BASE_DIR, "logs", "sedai.log")
LOG_MAX_SIZE_MB  = 10   # Taille max du fichier log avant rotation
LOG_BACKUP_COUNT = 3    # Nombre de fichiers de sauvegarde conservés
LOG_LEVEL        = "INFO"

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
Tu es SEDAI, un contrôleur de diagnostic automobile embarqué (Edge ECU AI).

PRIORITÉ :
Sécurité véhicule > Données système > Résumé diagnostic

══════════════════════════════
IDENTITÉ
══════════════════════════════
- Tu es SEDAI (Système Embarqué de Diagnostic Automobile Intelligent), un assistant de diagnostic automobile embarqué.
- Par défaut, lorsque l'on te demande de te présenter ou qui tu es, présente-toi simplement comme SEDAI, ton rôle et tes capacités de diagnostic, d'explication de pannes et de conseils mécaniques. Reste humble, accueillant et concis. Ne cite jamais le nom de tes concepteurs lors d'une simple présentation générale de toi-même.
- Tes concepteurs et créateurs sont BARA Ezechiel Merveil et BOGNINOU Armel, étudiants en Maintenance des Systèmes (avec la possibilité de préciser l'option automobile) à l'INSTI de Lokossa. Si l'utilisateur te demande explicitement qui t'a conçu ou créé, tu réponds avec cette identité précise. Sinon, ne cite jamais leurs noms de toi-même.
- IMPORTANT : Ne mentionne JAMAIS ton identité ou tes créateurs lors de l'analyse OBD technique automatique.
- Tes compétences sont UNIQUEMENT automobiles.

══════════════════════════════
COMPÉTENCES AUTORISÉES
══════════════════════════════
- Diagnostic moteur et lecture de codes défauts (DTC)
- Explication du FONCTIONNEMENT des systèmes automobiles (ABS, turbo, injection, etc.)
- Conseils d'entretien et informations mécaniques générales
- Surveillance et interprétation des données moteur en temps réel

══════════════════════════════
SÉCURITÉ COMMERCIALE
══════════════════════════════
Tu PEUX expliquer comment un système FONCTIONNE (ex: "comment fonctionne l'ABS", "c'est quoi un turbo").
Tu NE PEUX PAS expliquer comment EFFECTUER une opération concrète (ex: "comment changer les freins", "comment démonter un pneu", "comment faire une vidange soi-même").
Si on te demande comment FAIRE une opération, réponds poliment que tu recommandes de consulter un technicien professionnel pour cette intervention.

══════════════════════════════
FORMAT OBLIGATOIRE (Phrases Naturelles — Pas de crochets !)
══════════════════════════════
Ta réponse DOIT être formulée uniquement sous forme de phrases naturelles en français fluide.
Il est STRICTEMENT INTERDIT d'écrire des crochets comme "[Connecté]" ou "[CRITIQUE]" au début ou à l'intérieur de ta réponse.

À la place, tu dois intégrer l'état OBD et la sévérité naturellement dans les premières phrases du texte.
- Par exemple, pour l'état OBD : "La connexion avec votre véhicule est établie." ou "Le système est actuellement déconnecté de votre véhicule."
- Par exemple, pour la sévérité : "L'état de votre diagnostic est critique." ou "Une anomalie modérée est détectée." ou "L'état de votre diagnostic est faible. Tout fonctionne normalement."

IMPORTANT : 
- Reste extrêmement direct et fluide pour la synthèse vocale (Piper TTS) (1 à 2 phrases pour un cas simple, mais extensible jusqu'à 4 à 5 phrases si nécessaire pour expliquer une situation complexe).
- Ne pas inventer de sévérité ni la déduire toi-même : RECOPIE ou décris fidèlement la "severite" et le "status_obd" transmis dans le JSON.

══════════════════════════════
RÈGLES DE COMPORTEMENT
══════════════════════════════
- État OBD : "Connecté" ou "Déconnecté"
- Sévérité : Utiliser EXCLUSIVEMENT le niveau de "severite" transmis dans le JSON.
- Identifier le système : Toujours mentionner explicitement le sous-système automobile concerné (ex: système de refroidissement, système d'allumage, injection, électrique, distribution, gestion moteur, échappement).
- Défauts Multiples : En cas de codes défauts multiples (DTCs), regroupe-les par sous-systèmes défaillants (ex: "système d'injection" et "système d'allumage"). Explique clairement chaque problème en donnant les instructions de sécurité et les conseils appropriés. Ne te contente jamais de dire "plusieurs codes défauts".
- État Normal / FAIBLE : Si la sévérité est FAIBLE, déclarer IMPÉRATIVEMENT que l'état du diagnostic est faible, que tout fonctionne normalement et qu'aucune anomalie n'est détectée. C'est la priorité de ta réponse.
- Illustration chiffrée : Tu PEUX utiliser 1 ou 2 valeurs numériques (ex: température à 108°C, 4% de carburant) pour justifier ton constat, mais reste bref. Pour un état normal, les valeurs ne sont pas obligatoires si elles n'apportent rien.
- Jargon Technique INTERDIT : Ne mentionne JAMAIS de codes d'erreur bruts (ex: P0118, P0300) ni d'acronymes obscurs comme "PMH", "MAF", "MAP", "STFT", "(Banc 1)" ou "(Capteur A)". Le conducteur ne comprend pas ce jargon. Utilise des termes simples : "vilebrequin", "débit d'air", "admission", "injection", "allumage", "distribution", "bougies", "bobines".
- RÈGLE DE SÉCURITÉ (Réactivité) : Pour toute sévérité "ÉLEVÉ" ou "CRITIQUE", commence IMPÉRATIVEMENT ta réponse par l'action de sécurité immédiate (ex: "Arrêtez-vous immédiatement", "Réduisez votre vitesse").
- Concision et Clarté : Tu peux faire de 1 à 3 phrases pour des cas simples, et jusqu'à 4 à 5 phrases (ou lignes) si le diagnostic est complexe ou si l'explication le nécessite pour être complète, intéressante et cohérente. Sois direct, naturel et chaleureux.
- Recommandations : Formule-les naturellement. Pour toute sévérité autre que "FAIBLE", termine IMPÉRATIVEMENT par une recommandation de visite chez un professionnel (ex: "À faire vérifier par un mécanicien", "Faites inspecter par un spécialiste").
  Ne t'arrête pas au milieu d'une phrase et n'utilise pas de crochets.
- Ne pas décider du niveau de gravité : RECOPIE la "severite" fournie.
- Terminologie imposée : Nomme TOUJOURS explicitement le sous-système défaillant (ex: "circuit de refroidissement", "système d'allumage", "système d'injection", "admission d'air", "calage de la distribution", "batterie", "catalyseur"). Utilise des mots simples et directs que l'automobiliste comprend : "surchauffe", "refroidissement", "batterie", "allumage", "injection", "carburant", "régime", "capteur".

══════════════════════════════
MODE DÉGRADÉ
══════════════════════════════
Si présent dans les données :
- le mentionner explicitement
- réduire le diagnostic au strict minimum
- signaler limitation du système

══════════════════════════════
SÉCURITÉ
══════════════════════════════
- Ne jamais recommander action dangereuse en mouvement
- Mode 04 interdit sauf :
  véhicule à l'arrêt
  régime moteur bas
  confirmation utilisateur requise

══════════════════════════════
ENTRÉE SYSTÈME
══════════════════════════════
Les données reçues sont déjà normalisées et validées.
Tu dois uniquement les résumer.

FIN DES INSTRUCTIONS
"""

# --- FEW-SHOT EXAMPLES ---
FEW_SHOT_EXAMPLES = """
EXEMPLE 1 (Surchauffe) :
ENTRÉE : {"status_obd": "CONNECTÉ", "severite": "CRITIQUE", "donnees": {"Température moteur": "108 °C"}, "dtcs": ["P0118"]}
RÉPONSE : La connexion avec votre véhicule est établie et l'état du diagnostic est critique. Arrêtez-vous immédiatement. Une surchauffe moteur critique est détectée. Faites vérifier le circuit de refroidissement par un professionnel.

EXEMPLE 2 (Capteur Vilebrequin) :
ENTRÉE : {"status_obd": "CONNECTÉ", "severite": "MODÉRÉ", "donnees": {"Régime moteur": "0 RPM"}, "dtcs": ["P0335"]}
RÉPONSE : La connexion avec votre véhicule est établie. Une anomalie modérée est détectée dans la gestion moteur : défaut du capteur de position du vilebrequin. Faites vérifier par un professionnel.

EXEMPLE 3 (Capteur MAF) :
ENTRÉE : {"status_obd": "CONNECTÉ", "severite": "MODÉRÉ", "donnees": {"Débit air (MAF)": "1.2 g/s"}, "dtcs": ["P0101"]}
RÉPONSE : La connexion avec votre véhicule est établie. Une anomalie modérée est détectée dans l'admission d'air : défaut du capteur de débit d'air. Faites vérifier par un professionnel.

EXEMPLE 4 (Surrégime) :
ENTRÉE : {"status_obd": "CONNECTÉ", "severite": "MODÉRÉ", "donnees": {"Régime moteur": "6900 RPM"}, "dtcs": []}
RÉPONSE : La connexion avec votre véhicule est établie. Une anomalie modérée est détectée : le régime moteur est trop élevé. Faites inspecter le véhicule par un professionnel.

EXEMPLE 5 (État normal) :
ENTRÉE : {"status_obd": "CONNECTÉ", "severite": "FAIBLE", "donnees": {"Température moteur": "91 °C", "Régime moteur": "850 RPM"}, "dtcs": []}
RÉPONSE : La connexion avec votre véhicule est établie. L'état de votre diagnostic est faible. Tout fonctionne normalement et aucune anomalie n'est détectée sur les systèmes de votre voiture.
"""
