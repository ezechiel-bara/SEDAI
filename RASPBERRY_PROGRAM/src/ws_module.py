"""
ws_module.py — Serveur WebSocket bidirectionnel (Version Sécurisée v2.2)
Assure la communication avec l'application Flutter sans utiliser asyncio.
- Envoie les paramètres en temps réel à la fréquence WS_SEND_INTERVAL.
- Reçoit les actions (voice_activate, infos véhicule, commandes OBD).
- Détection dynamique de la carte audio ALSA.
- Protection contre le blocage des clients lents.
"""

import threading
import json
import time
import queue
import logging
import subprocess
import os
from typing import Dict, Any, Set, Optional

try:
    from websockets.sync.server import serve, ServerConnection
    import websockets.exceptions
except ImportError:
    serve, ServerConnection = None, None

import config as cfg

# Logger dédié
logger = logging.getLogger("WS")

class WebSocketModule(threading.Thread):
    """
    Module réseau synchrone (threadé) gérant un port bidirectionnel pour Flutter.
    """
    
    def __init__(self, shared_state: Dict[str, Any], state_lock: threading.Lock,
                 action_queue: queue.Queue, event_voice_active: threading.Event,
                 event_stop: threading.Event, obd_module: Any = None):
        """Initialise le serveur WebSocket."""
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.state_lock = state_lock
        self.action_queue = action_queue
        self.event_voice_active = event_voice_active
        self.event_stop = event_stop
        self.obd_module = obd_module
        
        self.clients_lock = threading.Lock()
        self.clients: Set[ServerConnection] = set()
        self._server = None
        
        # Cache de l'index de la carte audio ALSA
        self._audio_card_idx: str = self._detect_audio_card()

    def _detect_audio_card(self) -> str:
        """
        Détecte dynamiquement l'index de la carte son USB pour amixer.
        Cherche 'UACDemoV10' ou à défaut un périphérique 'USB'.
        """
        try:
            output = subprocess.check_output(["aplay", "-l"], stderr=subprocess.STDOUT).decode()
            for line in output.splitlines():
                if "card" in line.lower() and ("USB" in line or "UACDemoV10" in line):
                    # Exemple: card 2: UACDemoV10 [UACDemoV10], device 0...
                    parts = line.split(":")
                    card_part = parts[0].split()
                    if len(card_part) >= 2:
                        idx = card_part[1]
                        logger.info(f"[WS] Carte audio USB détectée à l'index {idx}.")
                        return idx
        except Exception as e:
            logger.warning(f"[WS] Échec de l'auto-détection audio : {e}. Utilisation index 2.")
        return "2"

    def broadcast_loop(self) -> None:
        """
        Boucle d'arrière-plan : diffuse l'état du système à tous les clients connectés.
        """
        logger.info("[WS] Démarrage de la boucle de diffusion (broadcast).")

        while not self.event_stop.is_set():
            if self.event_stop.wait(cfg.WS_SEND_INTERVAL):
                break

            # Vérifier s'il y a des clients avant de construire le payload
            with self.clients_lock:
                if not self.clients:
                    continue
                current_clients = list(self.clients)

            # Lecture sécurisée de l'état partagé
            with self.state_lock:
                obd_status      = self.shared_state.get("statut_obd", "déconnecté")
                obd_data        = dict(self.shared_state.get("obd_data", {}))
                dtcs            = list(self.shared_state.get("dtcs", []))
                dtcs_confirmes  = list(self.shared_state.get("dtcs_confirmes", []))
                dtcs_en_attente = list(self.shared_state.get("dtcs_en_attente", []))
                dtcs_permanents = list(self.shared_state.get("dtcs_permanents", []))
                derniere_transcription = self.shared_state.pop("derniere_transcription", None)
                dernier_rapport = self.shared_state.get("dernier_rapport")
                dernier_chat    = self.shared_state.pop("dernier_chat", None)
                ai_snapshot     = self.shared_state.get("obd_snapshot_ia")
                reconnect_info  = self.shared_state.get("obd_reconnect_info", {})
                reliability     = self.shared_state.get("reliability_score", 100.0)

            # Construction du payload
            payload = {
                "statut_obd": obd_status,
                "dtcs": dtcs,
                "dtcs_confirmes": dtcs_confirmes,
                "dtcs_en_attente": dtcs_en_attente,
                "dtcs_permanents": dtcs_permanents,
                "reliability_score": reliability
            }

            if obd_data:
                payload.update(obd_data)

            if ai_snapshot:
                payload["snapshot_ia"] = {
                    "features":  ai_snapshot.get("features_ia", {}),
                    "meta":      ai_snapshot.get("meta", {}),
                    "timestamp": ai_snapshot.get("timestamp", ""),
                }

            if dernier_rapport:
                payload["rapport"] = dernier_rapport.get("texte", "")
                # Priorité au score local du rapport s'il existe
                if "fiabilite" in dernier_rapport:
                    payload["reliability_score"] = dernier_rapport["fiabilite"]

            if dernier_chat:
                payload["chat"] = dernier_chat

            if derniere_transcription:
                payload["transcription"] = derniere_transcription

            if reconnect_info:
                payload["obd_reconnect"] = reconnect_info
                
            message_str = json.dumps(payload, ensure_ascii=False)
            
            # Envoi multi-clients avec protection contre les clients lents/morts
            dead_clients = set()
            for client in current_clients:
                try:
                    # send() peut bloquer si le buffer réseau est plein (client lent)
                    client.send(message_str)
                except Exception as e:
                    logger.debug(f"[WS] Perte de connexion client : {e}")
                    dead_clients.add(client)
            
            if dead_clients:
                with self.clients_lock:
                    for dc in dead_clients:
                        self.clients.discard(dc)

    def _send_snapshot(self, websocket: ServerConnection) -> None:
        """Envoie l'état immédiat lors de la connexion."""
        try:
            with self.state_lock:
                payload = {
                    "statut_obd":   self.shared_state.get("statut_obd", "déconnecté"),
                    "dtcs":         list(self.shared_state.get("dtcs", [])),
                    "dtcs_confirmes": list(self.shared_state.get("dtcs_confirmes", [])),
                    "dtcs_en_attente": list(self.shared_state.get("dtcs_en_attente", [])),
                    "dtcs_permanents": list(self.shared_state.get("dtcs_permanents", [])),
                    "reliability_score": self.shared_state.get("reliability_score", 100.0)
                }
                obd_data = self.shared_state.get("obd_data")
                if obd_data: payload.update(obd_data)
                
                ai_snapshot = self.shared_state.get("obd_snapshot_ia")
                if ai_snapshot:
                    payload["snapshot_ia"] = {
                        "features": ai_snapshot.get("features_ia", {}),
                        "meta":     ai_snapshot.get("meta", {}),
                    }
                
                reconnect = self.shared_state.get("obd_reconnect_info")
                if reconnect: payload["obd_reconnect"] = reconnect

            websocket.send(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def handle_client(self, websocket: ServerConnection) -> None:
        """Gère les commandes entrantes d'un client Flutter."""
        addr = websocket.remote_address
        logger.info(f"[WS] Client connecté : {addr}")

        with self.clients_lock:
            self.clients.add(websocket)

        self._send_snapshot(websocket)

        try:
            # Cette boucle bloque le thread tant que le client est connecté
            for message in websocket:
                if self.event_stop.is_set():
                    break

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                cmd = data.get("command") or data.get("action")
                if not cmd:
                    continue

                # --- Dispatcher de commandes ---
                if cmd == "voice_activate":
                    logger.info("[WS] Action : Activation PTT.")
                    self.event_voice_active.set()

                elif cmd == "voice_deactivate":
                    logger.info("[WS] Action : Désactivation PTT.")
                    self.event_voice_active.clear()

                elif cmd == "chat_message":
                    text = data.get("text", "").strip()
                    if text:
                        self.action_queue.put({"type": "free_chat", "source": "chat", "text": text})

                elif cmd == "diagnose":
                    logger.info("[WS] Demande de diagnostic manuel.")
                    self.action_queue.put({
                        "type": "diagnostic_request",
                        "source": "smartphone",
                        "text": "Demande smartphone."
                    })

                elif cmd == "vehicle_info":
                    infos = data.get("data", {})
                    if infos:
                        with self.state_lock:
                            self.shared_state["vehicle_info"] = infos
                        logger.info(f"[WS] Véhicule configuré : {infos.get('marque')} {infos.get('modele')}")

                elif cmd == "clear_dtcs":
                    if data.get("user_confirmed", False) and self.obd_module:
                        logger.warning("[WS] Ordre d'effacement des DTC reçu.")
                        self.obd_module.clear_dtc(confirmed=True)

                elif cmd == "set_volume":
                    level = data.get("level", cfg.DEFAULT_AUDIO_VOLUME)
                    self._set_hardware_volume(level)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[WS] Connexion fermée normalement : {addr}")
        except Exception as e:
            logger.error(f"[WS] Erreur client {addr} : {e}")
        finally:
            with self.clients_lock:
                self.clients.discard(websocket)

    def _set_hardware_volume(self, level: int) -> None:
        """Ajuste le volume via amixer sur la carte détectée."""
        try:
            idx = self._audio_card_idx
            # On tente d'appliquer à tous les contrôles (Speaker, PCM, etc.)
            res = subprocess.check_output(["amixer", "-c", idx, "scontrols"]).decode()
            for line in res.splitlines():
                if "'" in line:
                    ctrl = line.split("'")[1]
                    subprocess.run(["amixer", "-c", idx, "sset", ctrl, f"{int(level)}%", "unmute"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Persistance
            vfile = os.path.join(os.path.dirname(__file__), "volume_state.txt")
            with open(vfile, "w") as f:
                f.write(str(int(level)))
            logger.info(f"[WS] Volume matériel réglé à {level}% sur carte {idx}.")
        except Exception as e:
            logger.error(f"[WS] Échec réglage volume : {e}")

    def run(self) -> None:
        """Lance le serveur WebSocket."""
        if serve is None:
            logger.error("[WS] Bibliothèque 'websockets' manquante.")
            return
            
        logger.info(f"[WS] Serveur prêt sur {cfg.WS_HOST}:{cfg.WS_PORT}")
        
        # Démarrer le diffuseur
        threading.Thread(target=self.broadcast_loop, daemon=True).start()
        
        try:
            with serve(
                self.handle_client,
                cfg.WS_HOST,
                cfg.WS_PORT,
            ) as server:
                self._server = server
                server.serve_forever()
        except Exception as e:
            logger.error(f"[WS] Erreur critique serveur : {e}")
