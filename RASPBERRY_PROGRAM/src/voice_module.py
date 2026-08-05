"""
voice_module.py — Reconnaissance vocale (Vosk ASR)
Capture le son du microphone USB et le convertit en texte via Vosk hors ligne.
Fonctionne sur le principe du "Push-to-talk" : l'enregistrement est actif uniquement
lorsque le flag "voice_activate" est déclenché par Flutter.
"""

import logging
import threading
import json
import queue
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    Model, KaldiRecognizer = None, None

from config import *

logger = logging.getLogger("VOICE")

class VoiceModule(threading.Thread):
    """
    Module gérant l'écoute du microphone et sa transcription par le modèle Vosk.
    """
    
    def __init__(self, action_queue: queue.Queue, event_voice_active: threading.Event, event_stop: threading.Event):
        super().__init__(daemon=True)
        self.action_queue = action_queue
        self.event_voice_active = event_voice_active
        self.event_stop = event_stop
        
        self.model = None
        self.recognizer = None
        self.audio_queue = queue.Queue()  # File asynchrone pour éviter les blocages matériels
        self.needs_reinit = True  # Initialisation obligatoire lors du premier démarrage
        self._init_vosk()

    def _init_vosk(self) -> None:
        """Charge le modèle de reconnaissance vocale hors ligne Vosk en RAM."""
        if Model is None:
            logger.warning("[VOICE] AVERTISSEMENT : Bibliothèque Vosk non installée.")
            return
            
        try:
            logger.info(f"[VOICE] Chargement du modèle ASR depuis {VOSK_MODEL_PATH}...")
            self.model = Model(VOSK_MODEL_PATH)
            self.recognizer = KaldiRecognizer(self.model, VOSK_SAMPLE_RATE)
            logger.info("[VOICE] Modèle Vosk chargé avec succès.")
        except Exception as e:
            logger.error(f"[VOICE] Erreur lors du chargement du modèle Vosk : {e}")

    def _handle_command(self, text: str) -> None:
        """Analyse le texte transcrit et déclenche l'action correspondante."""
        text = text.lower().strip()

        # Feedback vocal supprimé car la transcription s'affiche dans l'UI (ChatFree)

        if any(kw in text for kw in VOICE_CMD_DIAGNOSE + VOICE_CMD_STATUS):
            self.action_queue.put({
                "type": "diagnostic_request",
                "source": "voice",
                "text": "Demande vocale du conducteur."
            })

        elif any(kw in text for kw in VOICE_CMD_DTCS):
            self.action_queue.put({
                "type": "get_dtcs",
                "source": "voice",
                "text": text
            })

        elif any(kw in text for kw in VOICE_CMD_CLEAR):
            self.action_queue.put({
                "type": "clear_dtcs",
                "source": "voice",
                "text": text
            })

        elif any(kw in text for kw in VOICE_CMD_REPEAT):
            self.action_queue.put({
                "type": "repeat_last",
                "source": "voice",
                "text": text
            })

        else:
            # Mode conversation libre — toute autre phrase
            self.action_queue.put({
                "type": "free_chat",
                "source": "voice",
                "text": text
            })

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback asynchrone appelé par PortAudio. Ne doit jamais bloquer."""
        if status:
            pass # Ignorer les warnings de buffer pour éviter de polluer les logs
            
        # On alimente la file uniquement si le PTT est actif
        if self.event_voice_active.is_set():
            try:
                self.audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

    def run(self) -> None:
        """Boucle du thread qui gère l'orchestration vocale asynchrone."""
        logger.info("[VOICE] Démarrage du thread de reconnaissance vocale (Vosk Asynchrone).")
        
        if self.model is None or sd is None:
            logger.error("[VOICE] Module vocal inopérant ou désactivé.")
            while not self.event_stop.is_set():
                self.event_stop.wait(1.0)
            return

        RESAMPLE_RATIO = AUDIO_CAPTURE_RATE // VOSK_SAMPLE_RATE  # = 1 si 16000 Hz natif
        mic_connected = False

        while not self.event_stop.is_set():
            try:
                # 1. Attendre que le bouton PTT soit activé (évite les blocages et l'usure de flux)
                if not self.event_voice_active.wait(timeout=0.1):
                    continue

                # 2. Bouton PTT activé ! Réinitialiser PortAudio uniquement si nécessaire (évite latence + plantages)
                if self.needs_reinit:
                    try:
                        logger.info("[VOICE] Réinitialisation de l'API PortAudio (SoundDevice)...")
                        sd._terminate()
                        sd._initialize()
                        self.needs_reinit = False
                    except Exception as e:
                        logger.warning(f"[VOICE] Échec de la réinitialisation PortAudio : {e}")

                # --- Détection du périphérique audio ---
                device_idx = AUDIO_INPUT_DEVICE
                if AUDIO_AUTO_DETECT:
                    try:
                        devices = sd.query_devices()
                        for i, dev in enumerate(devices):
                            if "USB" in dev['name'] and dev['max_input_channels'] > 0:
                                device_idx = i
                                break
                    except Exception as e:
                        logger.warning(f"[VOICE] Échec de l'auto-détection micro : {e}. Index par défaut {AUDIO_INPUT_DEVICE}.")
                        self.needs_reinit = True

                # 3. Ouvrir le flux à la demande (PTT actif)
                with sd.RawInputStream(samplerate=AUDIO_CAPTURE_RATE, blocksize=4000 * RESAMPLE_RATIO,
                                       dtype='int16', channels=AUDIO_CHANNELS,
                                       device=device_idx, callback=self._audio_callback) as stream:
                    
                    logger.info(f"[VOICE] Microphone activé (Index: {device_idx if device_idx is not None else 'Défaut'}).")
                    mic_connected = True
                    
                    accumulated_text = []
                    freeze_time = 0.0
                    
                    # Vider les résidus audio de la file avant de commencer
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except queue.Empty:
                            break

                    # Boucle d'acquisition active pendant que le PTT est pressé
                    while self.event_voice_active.is_set() and not self.event_stop.is_set():
                        try:
                            data = self.audio_queue.get(timeout=0.1)
                            freeze_time = 0.0  # Reset
                            
                            if RESAMPLE_RATIO == 1:
                                pcm_16k = bytes(data)
                            else:
                                pcm = np.frombuffer(data, dtype=np.int16)
                                remainder = len(pcm) % RESAMPLE_RATIO
                                if remainder != 0:
                                    pcm = pcm[:-remainder]
                                
                                if len(pcm) == 0:
                                    continue
                                    
                                pcm_16k = pcm.reshape(-1, RESAMPLE_RATIO).mean(axis=1).astype(np.int16).tobytes()
                            
                            if self.recognizer.AcceptWaveform(pcm_16k):
                                result = json.loads(self.recognizer.Result())
                                text = result.get("text", "")
                                if text:
                                    logger.info(f"[VOICE] Segment reconnu : '{text}'")
                                    accumulated_text.append(text)

                        except queue.Empty:
                            freeze_time += 0.1
                            # Tolérance de 5.0s pour le démarrage et la réactivité du matériel USB sur Pi 5
                            if freeze_time > 5.0:
                                logger.error("[VOICE] ALERTE : Le flux du microphone USB s'est figé (Hardware Timeout). Redémarrage forcé au prochain PTT...")
                                self.needs_reinit = True
                                mic_connected = False
                                break

                    # 4. PTT relâché : finaliser et envoyer
                    final_res = json.loads(self.recognizer.FinalResult())
                    final_text = final_res.get("text", "")
                    if final_text:
                        logger.info(f"[VOICE] Segment final reconnu : '{final_text}'")
                        accumulated_text.append(final_text)
                        
                    full_text = " ".join(accumulated_text).strip()
                    if full_text:
                        logger.info(f"[VOICE] Phrase complète envoyée à l'IA : '{full_text}'")
                        
                        # --- AJOUT: Envoyer la transcription au WebSocket ---
                        self.action_queue.put({
                            "type": "transcription",
                            "text": full_text
                        })
                        # ----------------------------------------------------
                        
                        self._handle_command(full_text)
                    
                    logger.info("[VOICE] Microphone désactivé (flux fermé proprement).")
                    mic_connected = False

            except Exception as e:
                self.needs_reinit = True
                if not mic_connected:
                    logger.error(f"[VOICE] Impossible d'ouvrir le microphone (Index {device_idx}, Rate {AUDIO_CAPTURE_RATE}Hz) : {e}")
                else:
                    logger.warning(f"[VOICE] Microphone déconnecté ou erreur de flux : {e}.")
                    mic_connected = False
                
                # Attendre avant de retenter la connexion (évite de saturer le CPU)
                self.event_stop.wait(2.0)
            
        logger.info("[VOICE] Arrêt du thread de reconnaissance vocale.")
