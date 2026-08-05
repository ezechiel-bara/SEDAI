import subprocess
import os
import sys

# Ajouter le dossier src
sys.path.append("c:\\code\\SEDAI\\src")
from config import *

model_file = os.path.join(PIPER_MODEL_PATH, PIPER_MODEL)
if not os.path.exists(model_file):
    print(f"Modèle introuvable à {model_file}")
    sys.exit(1)

# Options à tester
variations = {
    "orig_bogninou": "Bogninou",
    "bogue_ni_nou": "Bogue-ni-nou",
    "bo_gni_nou": "Bo-gni-nou",
    "bog_ni_nou": "bog-ni-nou",
    "boyinou": "boyinou",
    "bo_gny_nou": "bo-gny-nou"
}

venv_piper = os.path.join("c:\\code\\SEDAI", ".venv", "bin", "piper")
piper_bin = venv_piper if os.path.exists(venv_piper) else "piper"

for key, text in variations.items():
    wav_path = f"c:\\code\\SEDAI\\scratch\\test_{key}.wav"
    print(f"Génération de {key} pour le texte : '{text}' -> {wav_path}")
    piper_cmd = [piper_bin, "--model", model_file, "--output_file", wav_path]
    try:
        subprocess.run(piper_cmd, input=f"{text}\n".encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        print(" -> Réussi")
    except Exception as e:
        print(f" -> Échec : {e}")
