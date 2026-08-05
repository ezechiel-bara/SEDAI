# 🚀 Guide de Déploiement SEDAI

Bienvenue dans le guide d'installation étape par étape du **Système Embarqué de Diagnostic Automobile Intelligent (SEDAI)** sur Raspberry Pi 5. Ce guide est conçu pour être accessible à tous.

---

## 1. 🔌 Pré-requis matériels

Avant de commencer, assurez-vous de disposer du matériel suivant :
- **Raspberry Pi 5** (version 8 Go de RAM vivement recommandée pour faire tourner l'IA locale).
- **Carte SD** (capacité de 64 Go minimum, Classe 10 / A2 pour la vitesse d'écriture et la durabilité).
- **Alimentation USB-C** officielle Raspberry Pi (27W / 5.1V 5A). Indispensable pour l'inférence du modèle IA sans chute de performance.
- **Interface OBD-II vers USB** (base ELM327 ou compatible).
- **Microphone et Haut-parleur USB** (ou hub audio combiné USB).

---

## 2. 💿 Installation du système

### Installation de Raspberry Pi OS
1. Téléchargez et installez **Raspberry Pi Imager** sur votre ordinateur (Windows/Mac/Linux).
2. Insérez la carte SD (ou le lecteur microSD) dans votre ordinateur.
3. Dans Raspberry Pi Imager :
   - Choisissez le système d'exploitation : `Raspberry Pi OS (64-bit) Bookworm`.
   - Appliquez les réglages OS (l'icône « roue dentée ») : configurez votre Wi-Fi pour l'installation, activez **SSH**, et créez un utilisateur nommé `pi`.
   - Sélectionnez votre carte SD et cliquez sur **Écrire**.
4. Insérez la carte microSD flashée dans le Raspberry Pi 5 puis mettez-le sous tension.

### Configuration initiale
Connectez-vous au Raspberry Pi via SSH depuis le terminal (ou PowerShell) de votre ordinateur :
```bash
ssh pi@<adresse_ip_du_raspberry>
```
Une fois l'accès établi, mettez à jour votre système Debian :
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

---

## 3. 📦 Installation des dépendances

Le projet embarque un script prêt à l'emploi qui automatise l'installation, crée l'environnement virtuel Python (venv) et gère les paquets système apt.

1. Transférez le code source du projet SEDAI dans le dossier `/home/sedai/SEDAI`.
2. Placez-vous à la racine du projet :
```bash
cd /home/sedai/SEDAI
```
3. Rendez le script exécutable et lancez l'installation :
```bash
chmod +x install.sh
./install.sh
```
> *Note : Patientez durant cette phase. Le script va créer votre environnement (`.venv`), compiler les librairies audio (PyAudio) et configurer llama.cpp.*

---

## 4. ⚙️ Configuration du projet

### Structure des dossiers
Vérifiez que la racine se présente comme suit :
```text
/home/sedai/SEDAI/
├── src/                # Cœur logique
│   ├── config.py       # Configuration constante (ports, PIDs, seuils)
│   ├── main.py         # Point d'entrée
│   └── ...
├── install.sh          # Script Bash d'installation
├── requirements.txt    # Librairies pip
└── .venv/              # Environnement Python (généré automatiquement)
```

Placez impérativement vos modèles audio dans les répertoires dédiés, créés par le script `install.sh` :
- Extrayez le **Modèle Vosk** (ASR) dans : `/home/sedai/models/vosk/vosk-model-fr-0.22`
- Placez vos fichiers **Piper** (`.onnx` et `.json`) dans : `/home/sedai/models/piper/`
- Le **modèle GGUF** (llama.cpp) est téléchargé automatiquement au premier lancement dans : `/home/sedai/SEDAI/src/models/gemma-3-4b-it-Q4_K_M.gguf` (~2.5 Go, nécessite Internet une seule fois)

### Fichier config.py
Aucune variable d'environnement complexe n'est requise au niveau système. Pour paramétrer un port OBD spécifique, modifier le chemin du modèle LLM, ou ajuster les paramètres WebSocket, éditez simplement `src/config.py`.

---

## 5. 🟢 Lancement du système (Manuel)

Commencez toujours par tester le système manuellement afin de suivre les logs en direct via SSH :

```bash
cd /home/sedai/SEDAI

# Activation de l'environnement virtuel
source .venv/bin/activate

# Lancement classique
python3 src/main.py
```

Un flux d'informations indiquera les démarrages successifs des modules. La présence de `[SEDAI] Système Opérationnel` en fin de séquence confirme que tout est fonctionnel.

---

## 6. 🔄 Démarrage automatique (Daemon Tâche de Fond)

Pour un produit embarqué authentique, SEDAI doit s'activer automatiquement au démarrage du Raspberry Pi, sans intervention humaine.

1. Créez un fichier de service systemd :
```bash
sudo nano /etc/systemd/system/sedai.service
```

2. Collez-y la configuration suivante (adaptez `/home/sedai` si nécessaire) :
```ini
[Unit]
Description=SEDAI - Serveur de Diagnostic Automobile Intelligent
After=network.target sound.target

[Service]
ExecStart=/home/sedai/SEDAI/.venv/bin/python /home/sedai/SEDAI/src/main.py
WorkingDirectory=/home/sedai/SEDAI
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=sedai
User=pi
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
*Appuyez sur `CTRL+X`, puis `Y`, puis `Entrée` pour sauvegarder et quitter nano.*

3. Activez le service pour qu'il démarre à chaque boot :
```bash
sudo systemctl daemon-reload
sudo systemctl enable sedai.service
sudo systemctl start sedai.service
```

---

## 7. 🧪 Tests et Validation

Une fois SEDAI en service automatique, validez chaque interface matérielle :
- **OBD-II** : Mettez le contact et démarrez le véhicule. Le log `[OBD] Connecté` doit apparaître.
- **WebSocket** : Démarrez l'application Flutter et renseignez l'IP et le port `8765` du Raspberry Pi. Les indicateurs (RPM, Température, Vitesse) doivent se mettre à jour en temps réel.
- **Synthèse Vocale (Piper)** : Une phrase d'accueil est diffusée dès que l'orchestrateur a terminé son initialisation.
- **LLM (llama.cpp / Gemma)** : Utilisez le microphone ou le bouton dans Flutter pour envoyer une commande vocale. L'IA génère une réponse en interne et la restitue vocalement dans un délai de 2 à 5 secondes.

---

## 8. 🛠️ Dépannage (Troubleshooting)

En cas de comportements inattendus ou silencieux, procédez à une inspection :

- **Vérification rapide de l'état du service** :
```bash
sudo systemctl status sedai.service
```

- **Consultation des journaux Python en temps réel** :
```bash
journalctl -u sedai.service -f
```

- **Arrêt temporaire du service** :
```bash
sudo systemctl stop sedai.service
```

### ❌ Erreurs Courantes

- **Le port OBD ne se connecte pas** : L'interface ELM327 est parfois reconnue sous `/dev/ttyUSB1` plutôt que `/dev/ttyUSB0` selon l'ordre de branchement. Modifiez `OBD_PORT` dans `config.py` ou exécutez `dmesg | grep tty` pour identifier le bon identifiant.

- **Module Vosk/Piper plante (`Segmentation Fault`)** : La RAM est saturée. Assurez-vous d'utiliser un modèle GGUF quantifié (ex. `gemma-4b-q4.gguf`) et non un modèle en pleine précision. Le modèle doit tenir dans les 8 Go en coexistence avec Pi OS et les autres threads.

- **La voix Piper-TTS est silencieuse (ou erreur Python)** : La dépendance système C++ `espeak-ng` est manquante. Forcez son installation avec :
  ```bash
  sudo apt-get install espeak-ng
  ```

- **Aucune donnée Mode 06 (Ratés d'allumage par cylindre)** : L'extraction des ratés d'allumage utilise les adresses CAN hexadécimales modernes (MID `$A2` à `$A7`). Sur les véhicules plus anciens (protocole KWP2000 ou antérieurs à 2004), le véhicule ne répondra pas à ces requêtes. SEDAI ignorera silencieusement ces commandes sans planter.

- **Le modèle LLM est trop lent ou ne répond pas** : Vérifiez le chemin du fichier GGUF dans `config.py` (`LLM_MODEL_PATH`). Assurez-vous que le modèle est compatible avec llama.cpp et que les paramètres `N_THREADS` et `N_CTX` sont adaptés à votre matériel.
