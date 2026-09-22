#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialisation des répertoires des 5 modèles météo
===================================================
Ce script crée UNIQUEMENT la structure des répertoires et copie les assets
partagés (fond, frontières, communes, masque) vers chaque modèle.

IMPORTANT — indépendance stricte des données :
  Il ne copie JAMAIS les dalles météo d'un modèle vers un autre. Chaque modèle
  doit être rempli par son propre fetcher (pipeline/fetch_and_render_all.py).
  Copier les cartes AROME vers GFS/ECMWF/… produisait de fausses prévisions
  (bug historique : GFS et ECMWF affichaient les données AROME).
"""

import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

MODELS = ["arome", "arpege", "icon", "gfs", "ecmwf"]

# Assets purement géographiques, identiques pour tous les modèles
# (jamais de données météorologiques ici).
SHARED_ASSETS = ["fond.webp", "frontieres.svg", "communes.json", "mask_france.png"]


def setup_all_models():
    src_maps = os.path.join(OUTPUT_DIR, "maps")

    for model in MODELS:
        model_maps = os.path.join(OUTPUT_DIR, model, "maps")
        os.makedirs(model_maps, exist_ok=True)
        print(f"[setup] {model}/maps pret")

        for asset in SHARED_ASSETS:
            src = os.path.join(src_maps, asset)
            dst = os.path.join(model_maps, asset)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
                print(f"   -> copie asset partage {asset}")

    print("[setup] Structure des 5 modeles prete (aucune donnee meteo croisee).")


if __name__ == "__main__":
    setup_all_models()
