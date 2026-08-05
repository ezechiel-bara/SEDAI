"""
vehicle_pids_data.py — PIDs OBD-II spécifiques par marque/modèle
Structure extensible à compléter progressivement après validation terrain.

IMPORTANT : Les PIDs listés ici sont des noms de commandes python-obd STANDARDS
(pas de valeurs hexadécimales constructeur inventées).
Les PIDs propriétaires (Mode 21/22) sont réservés à une Phase 2
après validation sur véhicule réel.
"""

# Structure : VEHICLE_SPECIFIC_PIDS[marque][modele]["generique"] -> list[str]
# Chaque entrée est un nom de commande python-obd valide (ex: "SHORT_TERM_FUEL_TRIM_1").
# Si un modèle n'est pas listé, obd_module retourne [] et continue normalement.

VEHICLE_SPECIFIC_PIDS: dict = {
    "Toyota": {
        "Corolla": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
                # Température de transmission si supportée par l'ECU
                # "TRANS_TEMP",  # À décommenter après validation terrain
            ]
        },
        "Yaris": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "Hilux": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "ENGINE_LOAD",
                "FUEL_PRESSURE",
                "ENGINE_OIL_PRESSURE",
            ]
        },
        "RAV4": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "Land Cruiser": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "FUEL_PRESSURE",
                "ENGINE_LOAD",
                "ENGINE_OIL_PRESSURE",
            ]
        },
    },
    "Lexus": {
        "IS": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "RX": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
    },
    "Suzuki": {
        "Swift": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "Vitara": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
        "Jimny": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "FUEL_PRESSURE",
            ]
        },
    },
    "Hyundai": {
        "Tucson": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "i10": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
        "Accent": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
    },
    "Kia": {
        "Picanto": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
        "Sportage": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
    },
    "Nissan": {
        "Micra": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
            ]
        },
        "Patrol": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "FUEL_PRESSURE",
                "ENGINE_LOAD",
            ]
        },
        "Almera": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
    },
    "Mercedes": {
        "Classe C": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
                # PIDs spécifiques Mercedes (Mode 21/22) : TODO Phase 2
            ]
        },
        "Classe E": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
    },
    "BMW": {
        "Série 3": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
                "O2_B1S1",
                # PIDs spécifiques BMW (Mode 21/22) : TODO Phase 2
            ]
        },
        "Série 5": {
            "generique": [
                "SHORT_TERM_FUEL_TRIM_1",
                "LONG_TERM_FUEL_TRIM_1",
            ]
        },
    },
    # ---------------------------------------------------------------
    # Compléter progressivement après tests terrain sur chaque véhicule
    # Ne jamais inventer de valeurs hexadécimales PID constructeur
    # ---------------------------------------------------------------
}
