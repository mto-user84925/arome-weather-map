#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thunder_engine.py — Méthode Orages exacte de la page commune AROME
==================================================================
"""

import numpy as np

def compute_thunder_metrics(cape, refl, rain_1h=0.0, graupel=0.0):
    cape = np.maximum(0.0, np.asarray(cape, dtype=np.float32))
    refl = np.maximum(0.0, np.asarray(refl, dtype=np.float32))

    # Niveaux orageux exacts de la page commune : 0=Nul, 1=Faible, 2=Modéré, 3=Fort, 4=Violent
    code = np.zeros_like(cape, dtype=np.int16)
    code[(cape >= 100.0) | (refl >= 30.0)] = 1
    code[(cape >= 500.0) | (refl >= 40.0)] = 2
    code[(cape >= 1200.0) | (refl >= 50.0)] = 3
    code[(cape >= 2200.0) & (refl >= 52.0)] = 4
    code[refl >= 58.0] = 4

    # Conversion en pourcentage 0-100%
    prob_map = {0: 0.0, 1: 30.0, 2: 60.0, 3: 80.0, 4: 100.0}
    prob_orage = np.vectorize(prob_map.get)(code, 0.0)

    # Indice Foudre exact de la page commune
    lightning = np.clip((cape / 30.0) + np.maximum(refl - 25.0, 0.0) * 1.8, 0.0, 100.0)

    return prob_orage, lightning
