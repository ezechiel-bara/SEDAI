"""
logger_setup.py — Configuration centralisée des logs SEDAI
Initialise un système de logging avec rotation automatique et sortie console.
Doit être appelé UNE SEULE FOIS au démarrage depuis main.py.
"""

import logging
import logging.handlers
import os

from config import LOG_FILE_PATH, LOG_MAX_SIZE_MB, LOG_BACKUP_COUNT, LOG_LEVEL


def setup_logging() -> None:
    """
    Initialise le système de logging pour tous les modules SEDAI.

    Configure deux handlers :
    - Un fichier rotatif (RotatingFileHandler) qui conserve les derniers logs.
    - Une sortie console (StreamHandler) pour le débogage en direct.
    """
    # Créer le dossier logs s'il n'existe pas encore
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Format des messages de log
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler fichier avec rotation automatique
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Handler console (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configuration au niveau root — tous les loggers héritent de ce niveau
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Réduire le bruit des bibliothèques tierces
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logging.getLogger("SEDAI").info("=== Système de logging SEDAI initialisé ===")
