# 📱 SEDAI — Application Flutter (Windows / Android / Web)

Application **Flutter** multi-plateforme du système SEDAI.
Elle se connecte au **Raspberry Pi 5** via WebSocket pour afficher les données du véhicule en temps réel, lancer des diagnostics IA, interagir par la voix et générer des rapports PDF.

---

## ⚙️ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🖥️ **Dashboard temps réel** | 8 jauges radiales animées : vitesse, RPM, température, MAF, lambda, batterie, MAP, pression huile |
| 🔍 **Diagnostic IA** | Envoi d'une commande au Raspberry Pi → affichage du rapport généré par le LLM (Phi-3 / Gemma3) |
| 🎙️ **Push-to-Talk** | Activation/désactivation du micro USB branché sur le Raspberry Pi |
| 📋 **Historique** | Sauvegarde locale des diagnostics avec aperçu, détail et suppression |
| ⚙️ **Paramètres** | Modification de l'IP, du port WebSocket et des informations du véhicule |
| 📄 **Rapport PDF** | Génération d'un rapport de diagnostic imprimable (packages `pdf` + `printing`) |
| 🌙 **Thème sombre** | Interface moderne à thème automobile sombre (Material 3) |

---

## 📊 Jauges disponibles sur le Dashboard

| Jauge | Unité | Plage | PID OBD-II |
|---|---|---|---|
| Vitesse | km/h | 0 – 220 | `0x0D` |
| Régime moteur | RPM | 0 – 8 000 | `0x0C` |
| Température moteur | °C | 0 – 130 | `0x05` |
| Débit air (MAF) | g/s | 0 – 40 | `0x10` |
| Sonde Lambda (O₂) | λ | 0 – 1.5 | `0x14`–`0x1B` |
| Tension batterie | V | 10 – 15 | `0x42` |
| Pression MAP | kPa | 0 – 255 | `0x0B` |
| Pression huile | kPa | 0 – 600 | `0x5C` |

---

## 📁 Structure des fichiers

```
SEDAI_APP/
├── lib/
│   ├── main.dart                     → Point d'entrée — détection premier lancement
│   ├── core/
│   │   ├── constants.dart            → Couleurs, clés de stockage, constantes
│   │   └── theme.dart                → Thème sombre automobile (Material 3)
│   ├── models/
│   │   ├── vehicle_data.dart         → Modèle des données OBD-II temps réel
│   │   └── diagnosis_record.dart     → Modèle historique (sauvegarde locale)
│   ├── services/
│   │   ├── storage_service.dart      → SharedPreferences (IP, véhicule, historique)
│   │   └── websocket_service.dart    → Communication WebSocket ↔ Raspberry Pi
│   └── screens/
│       ├── setup_screen.dart         → Configuration initiale (premier lancement)
│       ├── main_screen.dart          → Navigation principale (3 onglets)
│       ├── dashboard_screen.dart     → Jauges OBD-II + boutons diagnostic/vocal
│       ├── analysis_screen.dart      → Résultat IA + sauvegarde
│       ├── history_screen.dart       → Historique local des diagnostics
│       └── settings_screen.dart      → Modifier IP, port, véhicule
├── windows/                          → Configuration build Windows
├── android/                          → Configuration build Android
├── web/                              → Configuration build Web
├── assets/                           → Images, polices, icônes
└── pubspec.yaml                      → Dépendances Flutter
```

---

## 🚀 Installation et lancement

### Prérequis

- [Flutter SDK](https://flutter.dev/docs/get-started/install) ≥ 3.0
- Windows 10 ou supérieur (pour le build Windows)
- Android SDK (pour le build Android)

### Commandes

```bash
# 1. Se placer dans le dossier
cd SEDAI/SEDAI_APP

# 2. Récupérer les dépendances
flutter pub get

# 3. Lancer sur Windows
flutter run -d windows

# 4. Lancer sur Android
flutter run

# 5. Lancer dans le navigateur (Chrome)
flutter run -d chrome
```

---

## 🔗 Connexion au Raspberry Pi

1. Assurez-vous que le Raspberry Pi est sur le **même réseau Wi-Fi** que votre appareil
2. Au premier lancement, l'application affiche un écran de configuration
3. Entrez l'**adresse IP** du Raspberry Pi (ex: `192.168.1.42`) et le **port** (`8765` par défaut)
4. L'application se connecte automatiquement via WebSocket

---

## 🛠️ Build de production

```bash
# Windows (exécutable .exe)
flutter build windows

# Android (APK)
flutter build apk --release

# Web (dossier build/web/)
flutter build web
```

---

## 📦 Dépendances Flutter

| Package | Version | Rôle |
|---|---|---|
| `web_socket_channel` | ^2.4.0 | Communication WebSocket avec le Raspberry Pi |
| `syncfusion_flutter_gauges` | ^33.1.45 | Jauges radiales animées du dashboard |
| `google_fonts` | ^6.3.3 | Police Exo (thème automobile) |
| `shared_preferences` | ^2.5.4 | Sauvegarde locale (IP, historique, véhicule) |
| `pdf` | ^3.12.0 | Génération de rapports PDF |
| `printing` | ^5.13.1 | Impression et export PDF |
| `intl` | ^0.19.0 | Formatage des dates |

---

## 🐛 Dépannage rapide

| Problème | Solution |
|---|---|
| `WebSocket connection failed` | Vérifier l'IP du Raspberry Pi dans Paramètres, s'assurer que `main.py` tourne |
| `Jauges figées à 0` | La connexion WebSocket est établie mais aucune donnée OBD ne remonte — vérifier l'ELM327 |
| `Erreur PathExistsException` au build Windows | Lancer `flutter clean` puis `flutter pub get` |
| `Rapport PDF vide` | Vérifier que le diagnostic a bien été reçu et sauvegardé dans l'historique |
