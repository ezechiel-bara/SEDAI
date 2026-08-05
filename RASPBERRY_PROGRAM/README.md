# 🔧 SEDAI — Programme Raspberry Pi 5

Programme Python embarqué sur **Raspberry Pi 5**, constituant le **cerveau du système SEDAI**.
Il lit les données de la voiture via OBD-II, les analyse avec une IA locale, parle à l'utilisateur par synthèse vocale, et envoie tout en temps réel à l'application Flutter via WebSocket.

---

## ⚙️ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🔌 **OBD-II** | Connexion à la voiture via adaptateur ELM327 (USB), lecture des PIDs et codes DTC |
| 🧠 **IA locale** | Analyse des pannes avec un LLM embarqué (Phi-3 Mini ou Gemma3 4B via llama.cpp) |
| 🎙️ **Voix entrante** | Reconnaissance vocale (STT) via Whisper — micro USB sur le Raspberry Pi |
| 🔊 **Voix sortante** | Synthèse vocale (TTS) via Piper — haut-parleur USB sur le Raspberry Pi |
| 📡 **WebSocket** | Serveur WebSocket sur le port `8765` — communication avec l'app Flutter |
| 📊 **Monitoring** | Lecture en temps réel de 8 PIDs : vitesse, RPM, température, MAF, lambda, batterie, MAP, pression huile |
| 🗃️ **Base DTC** | +2000 codes DTC OBD-II avec descriptions détaillées en français (`obd2_codes.py`) |
| 🧠 **Mémoire** | Historique de la conversation pour un contexte IA cohérent entre les échanges |

---

## 📁 Structure des fichiers

```
RASPBERRY_PROGRAM/
├── src/
│   ├── main.py                  → Point d'entrée — orchestration de tous les modules
│   ├── config.py                → Configuration globale (ports, chemins modèles, seuils)
│   ├── obd_module.py            → Communication OBD-II via python-obd (ELM327)
│   ├── obd_normalizer.py        → Normalisation et validation des données OBD brutes
│   ├── obd_safety.py            → Règles de sécurité OBD (limites, alertes)
│   ├── diagnostic_module.py     → Lecture des DTC, analyse IA, rapport de panne
│   ├── monitor_module.py        → Boucle de surveillance des 8 PIDs en temps réel
│   ├── voice_module.py          → Reconnaissance vocale STT (Whisper)
│   ├── tts_module.py            → Synthèse vocale TTS (Piper)
│   ├── ws_module.py             → Serveur WebSocket (envoi/réception des commandes Flutter)
│   ├── memory_module.py         → Mémoire conversationnelle (historique des échanges IA)
│   ├── event_bus.py             → Bus d'événements inter-modules (pub/sub)
│   ├── ecu_state_machine.py     → Machine d'état de l'ECU
│   ├── logger_setup.py          → Configuration des logs
│   ├── startup.py               → Séquence de démarrage du système
│   ├── vehicle_pids_data.py     → Définition des PIDs supportés
│   └── knowledge_base.json      → Base de connaissances automobile pour le LLM
├── obd2_codes.py                → Dictionnaire Python de 2000+ codes DTC OBD-II en français
├── docs/                        → Documentation technique complémentaire
├── tests/                       → Tests unitaires (pytest)
├── scratch/                     → Scripts utilitaires et expérimentaux
└── DEPLOYMENT.md                → 📖 Guide de déploiement complet sur Raspberry Pi
```

---

## 🚀 Installation

> 📖 **Guide complet étape par étape** : voir **[DEPLOYMENT.md](./DEPLOYMENT.md)**

### Résumé rapide

```bash
# 1. Cloner le projet sur le Raspberry Pi
git clone https://github.com/VOTRE_NOM/SEDAI.git
cd SEDAI/RASPBERRY_PROGRAM

# 2. Créer un environnement virtuel Python
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer le système
nano src/config.py   # Adapter les chemins, ports et paramètres

# 5. Lancer le programme
python src/main.py
```

---

## 🔩 Matériel requis

| Composant | Recommandation |
|---|---|
| Raspberry Pi | **Raspberry Pi 5** — 8 Go RAM (recommandé pour le LLM) |
| Carte SD | 64 Go minimum, Classe A2 |
| Alimentation | USB-C 27W officielle (5.1V / 5A) — indispensable pour l'IA |
| Interface OBD | Adaptateur **ELM327 USB** (privilégier USB sur Bluetooth) |
| Microphone | Microphone USB (reconnaissance vocale) |
| Haut-parleur | Haut-parleur USB ou jack 3.5mm (synthèse vocale) |

---

## 📡 Protocole WebSocket

Le programme expose un serveur WebSocket sur le port **`8765`**.

```
ws://192.168.X.X:8765
```

### Messages reçus depuis l'application Flutter

**Lancer un diagnostic IA :**
```json
{ "action": "diagnostic", "vehicle": { "marque": "Toyota", "modele": "Corolla", "moteur": "1.8L" } }
```

**Activer le microphone (Push-to-Talk) :**
```json
{ "action": "voice_activate", "vehicle": { "marque": "...", "modele": "...", "moteur": "..." } }
```

**Désactiver le microphone :**
```json
{ "action": "voice_deactivate" }
```

### Messages envoyés vers l'application Flutter

**Données OBD-II en temps réel :**
```json
{
  "type": "vehicle_data",
  "payload": { "vitesse": 65.0, "regime": 2200.0, "temp_moteur": 88.0, "maf": 12.5,
               "lambda": 0.98, "batterie": 13.8, "pression_map": 85.0, "pression_huile": 250.0 }
}
```

**Résultat du diagnostic IA :**
```json
{ "type": "diagnosis", "payload": { "text": "Rapport de l'IA ici…" } }
```

---

## 🧪 Lancer les tests

```bash
cd RASPBERRY_PROGRAM
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## 📄 Dépendances principales

| Package | Rôle |
|---|---|
| `python-obd` | Communication OBD-II avec l'adaptateur ELM327 |
| `websockets` | Serveur WebSocket pour l'application Flutter |
| `openai-whisper` | Reconnaissance vocale (Speech-to-Text) |
| `piper-tts` | Synthèse vocale rapide et locale (Text-to-Speech) |
| `llama-cpp-python` | Exécution du LLM local (Phi-3 Mini / Gemma3 4B) |

---

## 🐛 Dépannage rapide

| Problème | Solution |
|---|---|
| `No OBD device found` | Vérifier le branchement USB de l'ELM327, essayer `ls /dev/ttyUSB*` |
| `WebSocket refused` | Vérifier que `main.py` tourne et que le port 8765 est ouvert |
| `LLM trop lent` | Vérifier `N_THREADS` et `N_CTX` dans `config.py`, réduire le contexte |
| `TTS muet` | Vérifier la sortie audio avec `aplay -l` et le chemin du modèle Piper |
| `STT ne répond pas` | Vérifier le micro USB avec `arecord -l`, ajuster `AUDIO_DEVICE` dans `config.py` |
