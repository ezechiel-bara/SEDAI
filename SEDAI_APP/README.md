# AUTO JAPAN — Application Flutter de Diagnostic Automobile Intelligent

Application mobile Flutter pour le système embarqué de diagnostic automobile AUTO JAPAN (Bénin).

---

## Architecture de l'application

```
lib/
├── main.dart                     # Point d'entrée — détection premier lancement
├── core/
│   ├── constants.dart            # Couleurs, clés de stockage, constantes
│   └── theme.dart                # Thème sombre automobile (Material 3)
├── models/
│   ├── vehicle_data.dart         # Données OBD-II temps réel
│   └── diagnosis_record.dart     # Modèle historique (sauvegarde locale)
├── services/
│   ├── storage_service.dart      # SharedPreferences (IP, véhicule, historique)
│   └── websocket_service.dart    # Communication WebSocket ↔ Raspberry Pi
└── screens/
    ├── setup_screen.dart         # Écran de configuration (premier lancement)
    ├── main_screen.dart          # Navigation principale (3 onglets)
    ├── dashboard_screen.dart     # Jauges OBD-II + boutons diagnostic/vocal
    ├── analysis_screen.dart      # Affichage résultat IA + sauvegarde
    ├── history_screen.dart       # Historique local des diagnostics
    └── settings_screen.dart      # Modifier IP, port, véhicule
```

---

## Jauges disponibles sur le Dashboard

| Jauge          | Unité | Plage       | Source OBD-II    |
|----------------|-------|-------------|------------------|
| Vitesse        | km/h  | 0 – 220     | PID 0x0D         |
| Régime moteur  | RPM   | 0 – 8 000   | PID 0x0C         |
| Temp. moteur   | °C    | 0 – 130     | PID 0x05         |
| Débit air MAF  | g/s   | 0 – 40      | PID 0x10         |
| Lambda (O₂)    | λ     | 0 – 1.5     | PID 0x14–0x1B    |
| Batterie       | V     | 10 – 15     | PID 0x42         |
| Pression MAP   | kPa   | 0 – 255     | PID 0x0B         |
| Pression huile | kPa   | 0 – 600     | PID 0x5C         |

---

## Fonctionnalités

- **Premier lancement** : écran de configuration (IP Raspberry Pi, port, marque/modèle/moteur)
- **Dashboard** : 8 jauges radiales animées avec plages d'alerte colorées
- **Diagnostic IA** : envoi de la commande au Raspberry Pi + affichage du rapport (Phi-3 Mini / Gemma3 4B)
- **Push-to-Talk** : bouton microphone qui active/désactive l'écoute du microphone USB branché sur le Raspberry Pi
- **Historique** : sauvegarde locale des diagnostics avec aperçu, détail, et suppression
- **Paramètres** : modification de l'IP, du port et des informations véhicule à tout moment

---

## Installation

### Prérequis
- Flutter SDK ≥ 3.0
- Android SDK ou Xcode (pour iOS)

### Commandes

```bash
# Cloner / extraire le projet
cd auto_japan_diagnostic

# Installer les dépendances
flutter pub get

# Lancer sur Android
flutter run

# Construire l'APK
flutter build apk --release

# Construire pour iOS
flutter build ios --release
```

---

## Communication WebSocket avec le Raspberry Pi

### Format des messages envoyés (App → Raspberry Pi)

**Lancer un diagnostic IA :**
```json
{
  "action": "diagnostic",
  "vehicle": {
    "marque": "Toyota",
    "modele": "Corolla",
    "moteur": "1.8L essence"
  }
}
```

**Activer le microphone USB (Push-to-Talk) :**
```json
{
  "action": "voice_activate",
  "vehicle": { "marque": "...", "modele": "...", "moteur": "..." }
}
```

**Désactiver le microphone USB :**
```json
{ "action": "voice_deactivate" }
```

### Format des messages reçus (Raspberry Pi → App)

**Données OBD-II en temps réel :**
```json
{
  "type": "vehicle_data",
  "payload": {
    "vitesse": 65.0,
    "regime": 2200.0,
    "temp_moteur": 88.0,
    "maf": 12.5,
    "lambda": 0.98,
    "batterie": 13.8,
    "pression_map": 85.0,
    "pression_huile": 250.0
  }
}
```

**Résultat du diagnostic IA :**
```json
{
  "type": "diagnosis",
  "payload": {
    "text": "Rapport de l'IA ici…"
  }
}
```

---

## Dépendances Flutter

| Package                   | Version  | Rôle                           |
|---------------------------|----------|--------------------------------|
| web_socket_channel        | ^2.4.0   | Communication WebSocket        |
| syncfusion_flutter_gauges | ^23.1.36 | Jauges radiales animées        |
| google_fonts              | ^6.1.0   | Police Exo (thème automobile)  |
| shared_preferences        | ^2.2.2   | Stockage local (IP, historique)|
| flutter_animate           | ^4.2.0   | Animations d'interface         |
| intl                      | ^0.19.0  | Formatage des dates            |
