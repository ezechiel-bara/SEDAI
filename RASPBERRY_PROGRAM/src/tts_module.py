"""
tts_module.py — Synthèse vocale Text-To-Speech (Piper)
Gère une file d'attente de messages à lire à voix haute via le haut-parleur USB.
Utilise Piper TTS pour la génération vocale locale et aplay (ALSA) pour la lecture.
Ajuste dynamiquement le débit de parole (calme ou pressé) selon le niveau d'urgence.
Permet d'interrompre instantanément la parole en cours pour diffuser une alerte critique.
Fonctionne dans un thread dédié (daemon).
"""

import threading
import queue
import subprocess
import os
import logging
import time

from config import *

# Configuration du logger pour le module TTS
logger = logging.getLogger("TTS")

class TTSModule(threading.Thread):
    """
    Module générant et lisant la voix à partir de texte en utilisant Piper TTS.
    Gère une file d'attente et ajuste le ton de la voix selon l'urgence mécanique.
    """
    
    def __init__(self, event_stop: threading.Event):
        """
        Initialise le module TTS.
        
        Args:
            event_stop (threading.Event): Événement pour stopper proprement le thread.
        """
        super().__init__(daemon=True)
        self.message_queue: queue.Queue = queue.Queue()
        self.event_stop = event_stop
        
        # Verrou de synchronisation pour interrompre de manière sécurisée la lecture
        self.process_lock = threading.Lock()
        self.current_process = None

        # Initialisation automatique du volume de la carte USB en lisant la dernière sauvegarde
        try:
            # Détection dynamique de l'index de la carte audio
            audio_idx = "2"
            try:
                output = subprocess.check_output(["aplay", "-l"], stderr=subprocess.STDOUT).decode()
                for line in output.splitlines():
                    if "card" in line.lower() and ("USB" in line or "UACDemoV10" in line):
                        parts = line.split(":")
                        card_part = parts[0].split()
                        if len(card_part) >= 2:
                            audio_idx = card_part[1]
                            break
            except Exception:
                pass

            logger.info(f"[TTS] Restauration du volume matériel sur la carte {audio_idx}...")
            
            # Lecture du volume sauvegardé
            saved_volume = DEFAULT_AUDIO_VOLUME # Défaut si pas de fichier
            volume_file = os.path.join(os.path.dirname(__file__), "volume_state.txt")
            if os.path.exists(volume_file):
                with open(volume_file, "r") as f:
                    try:
                        saved_volume = int(f.read().strip())
                    except ValueError:
                        pass
            
            # Récupération de la liste des contrôles (PCM, Speaker, etc.)
            result = subprocess.check_output(["amixer", "-c", audio_idx, "scontrols"], stderr=subprocess.STDOUT)
            controls = result.decode().splitlines()
            
            for line in controls:
                if "'" in line:
                    control_name = line.split("'")[1]
                    # On applique le volume restauré
                    subprocess.run(["amixer", "-c", audio_idx, "sset", control_name, f"{saved_volume}%", "unmute"], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning(f"[TTS] Échec de la restauration du volume : {e}")

    def speak(self, text: str, priority: int = 0) -> None:
        """
        Ajoute un message à la file d'attente vocale avec une priorité et un ton adaptés.
        La priorité 2 (CRITIQUE) efface la file d'attente et interrompt immédiatement toute lecture en cours.
        
        Args:
            text (str): Le texte à lire à voix haute.
            priority (int): Niveau de priorité explicite (0=normal/calme, 1=warning/info, 2=critique/urgence).
        """
        if not text or not str(text).strip():
            return
            
        text = str(text).strip()
        text_lower = text.lower()
        
        # Détection dynamique de priorité basée sur le contenu (fail-safe de sécurité)
        critical_keywords = [
            "surchauffe", "critique", "arrêt immédiat", "danger", "pression d'huile", 
            "arrêt moteur", "moteur imminent", "immédiate", "immédiat", "grave", "sécurité"
        ]
        warning_keywords = [
            "dégradé", "attention", "anomalie", "défaut", "erreur", "tension", 
            "carburant", "réservoir", "faible", "limité"
        ]
        
        if any(kw in text_lower for kw in critical_keywords):
            priority = max(priority, 2)
        elif any(kw in text_lower for kw in warning_keywords):
            priority = max(priority, 1)

        # Si alerte critique, on purge la file d'attente et on coupe le haut-parleur immédiatement
        if priority >= 2:
            logger.info("[TTS] ALERTE CRITIQUE : Purge de la file et interruption de la voix en cours.")
            self.clear_queue()
            
            with self.process_lock:
                if self.current_process is not None:
                    try:
                        self.current_process.kill()
                        logger.info("[TTS] Lecture en cours interrompue avec succès pour l'urgence mécanique.")
                    except Exception as e:
                        logger.warning(f"[TTS] Impossible d'interrompre le processus aplay : {e}")

        self.message_queue.put((text, priority))

    def clear_queue(self) -> None:
        """
        Vide la file d'attente vocale proprement.
        """
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                self.message_queue.task_done()
            except queue.Empty:
                break

    def play_text(self, text: str, priority: int = 0) -> None:
        """
        Génère l'audio avec Piper et le lit immédiatement via ALSA (aplay).
        Ajuste le rythme de parole (de calme à très urgent) selon la priorité.
        """
        logger.info(f"[TTS] Synthèse et lecture [Priorité {priority}] : {text}")
        
        # Réglage du débit de parole (length_scale) : plus bas = plus rapide et direct
        if priority >= 2:
            length_scale = 0.80  # Débit rapide, ton d'urgence
        elif priority == 1:
            length_scale = 0.98  # Débit normal, ton informatif
        else:
            length_scale = 1.05  # Débit légèrement ralenti, ton calme, posé et poli

        import re

        # Table d'expansions phonétiques rigoureuse pour les unités physiques et les sigles automobiles
        expansions = {
            # Unités de mesure physiques
            r"\bkm/h\b": "kilomètres par heure",
            r"\bkm\b": "kilomètres",
            r"\bRPM\b": "tours par minute",
            r"\brpm\b": "tours par minute",
            r"\bV\b": "volts",
            r"\bV\.\b": "volts",
            r"\b%\b": "pourcent",
            r"\bg/s\b": "grammes par seconde",
            r"\bkPa\b": "kilopascals",
            r"\b°C\b": "degrés Celsius",
            r"\b°\b": "degrés",
            r"\bA\b": "ampères",
            r"\bAh\b": "ampères-heures",
            r"\bHz\b": "hertz",
            r"\bms\b": "millisecondes",
            
            # Sigles automobiles et projet
            r"\bSEDAI\b": "Sédayi",
            r"\bSedai\b": "Sédayi",
            r"\bsedai\b": "sédayi",
            r"\bOBD-II\b": "o b d deux",
            r"\bOBDII\b": "o b d deux",
            r"\bOBD\b": "o b d",
            r"\bOBD 2\b": "o b d deux",
            r"\bDTC\b": "d t c",
            r"\bDTCs\b": "d t c",
            r"\bECU\b": "écu",
            r"\bABS\b": "a b s",
            r"\bPMH\b": "point mort haut",
            r"\bMAF\b": "débit d'air",
            r"\bMAP\b": "pression d'admission",
            r"\bSTFT\b": "correction carburant court terme",
            r"\bLTFT\b": "correction carburant long terme",
            r"\bINSTI\b": "insti",
            r"\bInsti\b": "insti",
            r"\binsti\b": "insti",
            
            # Prononciation parfaite des concepteurs par Piper TTS
            r"\bBARA\b": "Bara",
            r"\bEzechiel\b": "Ézéquiel",
            r"\bezéchiel\b": "Ézéquiel",
            r"\bezechiel\b": "Ézéquiel",
            r"\bMerveil\b": "Merveille",
            r"\bmerveil\b": "Merveille",
            r"\bBOGNINOU\b": "Boyinou",
            r"\bBogninou\b": "Boyinou",
            r"\bbogninou\b": "boyinou",
            r"\bArmel\b": "Armel",
            r"\barmel\b": "Armel",
        }

        spoken_text = text
        for pattern, replacement in expansions.items():
            spoken_text = re.sub(pattern, replacement, spoken_text)

        model_file = os.path.join(PIPER_MODEL_PATH, PIPER_MODEL)
        
        if not os.path.exists(model_file):
            logger.error(f"[TTS] ERREUR : Le modèle vocal Piper est introuvable à {model_file}")
            return

        for attempt in range(2):
            try:
                wav_path = "/tmp/sedai_tts.wav"
                
                # ÉTAPE 1 : Génération du fichier WAV avec Piper avec réglage de débit
                venv_piper = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "bin", "piper")
                piper_bin = venv_piper if os.path.exists(venv_piper) else "piper"
                piper_cmd = [piper_bin, "--model", model_file, "--output_file", wav_path, "--length_scale", str(length_scale)]
                
                try:
                    subprocess.run(piper_cmd, input=f"{spoken_text}\n".encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                except FileNotFoundError:
                    piper_cmd[0] = "piper-tts"
                    subprocess.run(piper_cmd, input=f"{spoken_text}\n".encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                
                # ÉTAPE 2 : Lecture propre du fichier WAV par l'ALSA (aplay)
                aplay_cmd = ["aplay", "-D", AUDIO_OUTPUT_DEVICE, wav_path]
                
                with self.process_lock:
                    # Annulation de dernière seconde si une alerte urgente vient de survenir pendant l'inférence Piper
                    if priority < 2 and any(isinstance(item, tuple) and item[1] >= 2 for item in list(self.message_queue.queue)):
                        logger.info("[TTS] Synthèse normale annulée en faveur d'une alerte prioritaire.")
                        break
                        
                    p_aplay = subprocess.Popen(aplay_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    self.current_process = p_aplay
                
                stderr_aplay = b""
                try:
                    _, stderr_aplay = p_aplay.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    logger.warning("[TTS] Timeout aplay, kill du processus...")
                    p_aplay.kill()
                    _, stderr_aplay = p_aplay.communicate()
                finally:
                    with self.process_lock:
                        self.current_process = None

                err_aplay = stderr_aplay.decode().strip() if stderr_aplay else ""
                
                # Si le périphérique est occupé ou n'est pas prêt
                if ("No such device" in err_aplay or "busy" in err_aplay.lower()) and attempt == 0:
                    logger.warning(f"[TTS] Matériel occupé ou non prêt ({err_aplay}). Retry dans 3s...")
                    time.sleep(3)
                    continue
                
                if p_aplay.returncode != 0 and err_aplay:
                    logger.error(f"[TTS] Erreur aplay (code {p_aplay.returncode}) : {err_aplay}")
                
                break # Succès
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"[TTS] Erreur de génération Piper : {e.stderr.decode().strip()}")
                break
            except Exception as e:
                logger.error(f"[TTS] Erreur critique dans la chaîne audio : {e}")
                break
                
        # Nettoyage
        try:
            if os.path.exists("/tmp/sedai_tts.wav"):
                os.remove("/tmp/sedai_tts.wav")
        except:
            pass

    def run(self) -> None:
        """Boucle du thread traitant la file d'attente de messages."""
        logger.info("[TTS] Démarrage du thread de synthèse vocale.")
        
        while not self.event_stop.is_set():
            try:
                # Attente bloquante mais avec timeout
                item = self.message_queue.get(timeout=0.5)
                
                if isinstance(item, tuple):
                    text, priority = item
                else:
                    text, priority = item, 0
                    
                self.play_text(text, priority)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[TTS] Erreur inattendue dans la boucle TTS : {e}")
                
        logger.info("[TTS] Arrêt du thread TTS.")
