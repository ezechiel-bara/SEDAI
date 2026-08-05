# 📡 Guide de Configuration : Connexion SEDAI au Raspberry Pi

Ce guide décrit les étapes pour connecter l'application Flutter **SEDAI Diagnostic** à votre **Raspberry Pi 5**.

---

## 🔧 Étape 1 : Configuration du Réseau

Le téléphone et le Raspberry Pi doivent être sur le **même réseau**.

### Option A : Le Raspberry Pi est un Point d'Accès (Recommandé en voiture)
1. Le Pi crée son propre Wi-Fi (ex: `SEDAI-CAR`).
2. Connectez votre téléphone à ce réseau Wi-Fi.
3. L'adresse IP du Pi sera généralement : **`192.168.4.1`**

### Option B : Wi-Fi Domestique (Pour les tests)
1. Connectez le Pi et le téléphone au même routeur Wi-Fi.
2. Trouvez l'IP du Pi en tapant `hostname -I` sur le Pi.
   * *Exemple : 192.168.1.42*

---

## 🚀 Étape 2 : Démarrer le Backend sur le Pi

Assurez-vous que le serveur WebSocket est en cours d'exécution sur votre Raspberry Pi.

```bash
cd ~/SEDAI
source venv/bin/activate
python main.py
```

Le serveur écoute par défaut sur le port **`8765`**.

---

## 📱 Étape 3 : Configurer l'Application

Lors du premier lancement de l'application (ou dans les Réglages) :

1. **Adresse IP** : Saisissez l'IP configurée à l'Étape 1 (ex: `192.168.4.1`).
2. **Port** : Gardez le port par défaut `8765`.
3. **Véhicule** : Remplissez les informations de votre voiture pour que l'IA puisse adapter ses diagnostics.
4. Appuyez sur **DÉMARRER** ou **ENREGISTRER**.

---

## ✅ Vérification de la Connexion

*   **Icône Verte (Connecté)** : L'application reçoit les données du Pi.
*   **Icône Rouge (Déconnecté)** : Vérifiez que l'IP est correcte et que le serveur tourne sur le Pi.

### Dépannage Rapide
*   **Ping** : Essayez de "pinger" l'IP du Pi depuis un terminal sur votre téléphone.
*   **Pare-feu** : Si la connexion est refusée, tapez `sudo ufw allow 8765` sur le Raspberry Pi.
