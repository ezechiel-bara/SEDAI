# 3.2 Procédure de Test

Cette procédure de test a pour objectif de valider le fonctionnement, la fiabilité et l'efficacité du système embarqué SEDAI, en vérifiant la bonne exécution des logiques matérielles et logicielles. Elle s'assurera de la bonne communication entre le boîtier et l'application mobile, du fonctionnement de l'intelligence artificielle pour l'assistance vocale, ainsi que de la surveillance continue des données du véhicule.

---

## Protocole 1 : Démarrage, Configuration et Connexion

- **Lancement du Boîtier :** Mettre sous tension le Raspberry Pi. Le système lance automatiquement ses composants internes (intelligence artificielle, gestion de la connexion et module vocal).
- **Liaison Véhicule :** Vérifier que le boîtier cherche et réussit à se lier silencieusement au véhicule (module OBD).
- **Lancement de l'Application :** Ouvrir l'application mobile SEDAI pour la toute première fois sur le smartphone.
- **Configuration Initiale :** Renseigner les informations du véhicule et configurer la connexion au boîtier dans l'application.
- **Critère de Succès :** Dès que la liaison est établie, le tableau de bord de l'application s'anime pour afficher les données du moteur en temps réel. Lors d'une fermeture puis réouverture de l'application, les paramètres de connexion et du véhicule sont bien mémorisés.

---

## Protocole 2 : Surveillance Continue et Alerte d'Anomalie (IA)

- **Induction d'une Anomalie :** Simuler un problème sur le véhicule (par exemple, induire artificiellement une surchauffe moteur ou débrancher un capteur pendant le trajet).
- **Analyse par l'IA :** Laisser le boîtier SEDAI analyser les données entrantes.
- **Affichage et Sauvegarde :** Observer la réaction de l'application mobile SEDAI.
- **Critère de Succès :** Le boîtier détecte l'anomalie en temps réel et l'IA alerte immédiatement le conducteur par la voix. En parallèle, l'application affiche instantanément le diagnostic à l'écran et le sauvegarde automatiquement en arrière-plan.

---

## Protocole 3 : Interaction avec l'Assistant Vocal

- **Requête du Conducteur :** Pendant que le système lit les données (boucle de surveillance active), poser une question à tout moment via le microphone (ex : *"Quel est l'état du moteur ?"* ou *"Quelle est la température ?"*).
- **Traitement de l'IA :** Attendre la réponse de l'intelligence artificielle.
- **Critère de Succès :** L'IA comprend la demande et y répond vocalement de manière pertinente, sans que cela n'interrompe la transmission continue des données du moteur vers l'application mobile.

---

## Protocole 4 : Navigation et Historique de l'Application Mobile

- **Exploration du Tableau de Bord :** Vérifier le suivi des jauges en temps réel et l'interface de l'assistant vocal depuis le premier espace.
- **Consultation de l'Historique :** Naviguer vers le deuxième espace ("Historique"). Ouvrir le rapport d'anomalie généré lors du Protocole 2.
- **Navigation Paramètres :** Accéder au troisième espace ("Paramètres") pour vérifier les options disponibles.
- **Critère de Succès :** La navigation entre les trois espaces de l'application est fluide. L'utilisateur peut facilement relire les anciens rapports sauvegardés dans l'historique.

---

## Protocole 5 : Test de Résilience et de Reconnexion Automatique

- **Indisponibilité du Boîtier :** Éteindre ou déconnecter brusquement le boîtier SEDAI pendant l'utilisation de l'application (synchronisation en direct en cours).
- **Signalisation :** Observer le comportement sur le tableau de bord de l'application.
- **Rétablissement :** Rallumer le boîtier SEDAI.
- **Critère de Succès :** Dès la coupure, un indicateur signale à l'écran que le boîtier est indisponible et l'application entame des tentatives de reconnexion automatique. Dès que le boîtier est à nouveau disponible, la liaison se rétablit seule et le tableau de bord s'anime à nouveau.

---

## Protocole 6 : Chat Textuel avec l'Intelligence Artificielle *(Fonctionnalité Complémentaire)*

- **Accès au Chat :** Depuis le tableau de bord de l'application, et uniquement lorsque le véhicule est à l'arrêt (vitesse = 0 km/h), appuyer sur l'icône de chat située dans la barre de navigation supérieure (AppBar) pour ouvrir l'interface de conversation textuelle.
- **Envoi d'un Message Simple :** Saisir un message de salutation (ex : *"Bonjour"*) dans la zone de texte et envoyer. Observer l'apparition d'un indicateur de chargement (cercle animé) signalant que l'IA est en train de formuler sa réponse.
- **Réception de la Réponse :** Attendre la réponse de l'IA dans la bulle de discussion.
- **Requête Technique :** Envoyer une question technique (ex : *"Quel est l'état de mon moteur ?"* ou *"Y a-t-il des codes défauts détectés ?"*). Vérifier que la réponse est bien en rapport avec les données OBD du véhicule.
- **Test de Restriction de Réparation :** Demander un tutoriel de réparation (ex : *"Comment changer ma courroie de distribution ?"*). Vérifier que le système refuse catégoriquement de fournir des instructions et oriente l'utilisateur vers un professionnel qualifié.
- **Test du Verrouillage en Conduite :** Mettre le véhicule en mouvement (vitesse > 0 km/h). Vérifier que la zone de saisie de texte est automatiquement désactivée et remplacée par un message *"Chat textuel désactivé en roulant"* accompagné d'une icône de cadenas.
- **Critère de Succès :** L'IA répond naturellement aux salutations sans mentionner de données techniques. Elle fournit des informations pertinentes et précises pour les questions techniques. Elle refuse les demandes de tutoriels de réparation. La saisie de texte est correctement verrouillée dès que le véhicule est en mouvement, garantissant la sécurité du conducteur.
