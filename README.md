# SEDAI Système Embarqué de Diagnostic Automobile Intelligent

SEDAI est un système complet de diagnostic automobile intelligent, conçu pour fonctionner sur **Raspberry Pi 5** et communicant avec une application **Flutter** sur PC/mobile via WebSocket.

---

## 📁 Structure du projet

```
SEDAI/
├── RASPBERRY_PROGRAM/   → Cerveau du système : IA, OBD-II, voix, diagnostic
└── SEDAI_APP/           → Application Flutter (Windows/Android/Web)
```

---

## 🧩 Les deux composants

### [RASPBERRY_PROGRAM](./RASPBERRY_PROGRAM/README.md)
Programme Python embarqué sur le **Raspberry Pi 5**. Il :
- Se connecte à la voiture via le port **OBD-II (ELM327)**
- Lit les codes défauts (DTC), les PIDs en temps réel
- Utilise une **IA locale** (LLM) pour analyser et expliquer les pannes en voix
- Expose les données via un **serveur WebSocket** pour l'application Flutter

### [SEDAI_APP](./SEDAI_APP/README.md)
Application **Flutter** multi-plateforme. Elle :
- Se connecte au Raspberry Pi via WebSocket
- Affiche les données du véhicule en temps réel (jauges, graphiques)
- Permet de lire et effacer les codes DTC
- Génère des rapports PDF de diagnostic

---

## Démarrage rapide

1. Déployer le programme sur le Raspberry Pi → voir [RASPBERRY_PROGRAM/README.md](./RASPBERRY_PROGRAM/README.md)
2. Lancer l'application Flutter → voir [SEDAI_APP/README.md](./SEDAI_APP/README.md)

---

## Technologies utilisées

| Composant         | Technologie                          |
|-------------------|--------------------------------------|
| Raspberry Pi      | Python 3, python-OBD, WebSocket      |
| IA embarquée      | LLM local (llama.cpp / Ollama)       |
| Voix              | TTS (Piper), STT (Whisper)           |
| Application       | Flutter / Dart                       |
| Communication     | WebSocket (ws)                       |
| Diagnostic OBD    | ELM327, protocoles OBD-II            |

---

## 📄 Licence

Ce projet est développé dans le cadre du projet **SEDAI**. Tous droits réservés.

---

## Auteur
BARA Olagnandjou Oluwadunni Ezechiel Merveil

> 🌍 Bénin | 🔗 [LinkedIn](https://www.linkedin.com/in/ezechiel-bara)
