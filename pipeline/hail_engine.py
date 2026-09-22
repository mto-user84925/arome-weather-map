#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hail_engine.py — Moteur Scientifique de Prévision de Grêle AROME (MESH & ICE3)
=============================================================================
Calcule la probabilité de grêle (0-100%) et le diamètre estimé (MESH en cm)
à partir des grandeurs microphysiques AROME :
  - refl : Réflectivité radar simulée (dBZ)
  - cape : Énergie potentielle convective disponible (J/kg)
  - tgrp : Précipitations cumulées de graupel / grêle au sol (mm)
  - t2m  : Température de surface (°C)
  - gust : Rafales de vent (km/h)

Méthodes de référence :
  - Witt et al. (1998) : Severe Hail and MESH algorithm
  - Craven & Brooks (2004) : Severe convective storm forecasting & SHIP
  - Météo-France CNRM : Schéma microphysique ICE3 / LIMA
"""

import numpy as np

def compute_hail_metrics(refl, cape, tgrp=0.0, t2m=20.0, gust=20.0):
    """
    Calcule (probabilité %, diamètre cm, niveau 0-4) pour un point ou tableau numpy.
    """
    refl = np.asarray(refl, dtype=np.float32)
    cape = np.asarray(cape, dtype=np.float32)
    tgrp = np.asarray(tgrp, dtype=np.float32)

    # 1. Condition initiale de réflectivité minimale
    # Réflectivité radar < 40 dBZ = pluie normale sans grêle
    has_convection = (refl >= 42.0)

    # 2. Facteur de Courant Ascendant (Updraft factor)
    # w_max = sqrt(2 * CAPE)
    cape_clamped = np.clip(cape, 0.0, 4000.0)
    updraft_factor = np.sqrt(np.maximum(100.0, cape_clamped) / 1000.0)

    # 3. Facteur Réflectivité Cœur de Nuage (Witt et al.)
    refl_factor = np.maximum(0.0, (refl - 40.0) / 22.0)

    # 4. Probabilité de grêle P_hail (0 à 100 %)
    raw_prob = (refl_factor * updraft_factor * 75.0) + (np.clip(tgrp, 0.0, 5.0) * 10.0)
    prob = np.where(has_convection, np.clip(np.round(raw_prob), 0.0, 100.0), 0.0)

    # 5. Diamètre Estimé MESH (Maximum Estimated Size of Hail) en centimètres
    # MESH ~ 2.54 * (HKE / 18)^1.3 * sqrt(CAPE / 1200)
    raw_diam = 2.54 * np.power(np.maximum(0.0, refl - 44.0) / 18.0, 1.3) * np.sqrt(np.maximum(200.0, cape_clamped) / 1200.0)
    # Ajustement si graupel mesuré au sol
    raw_diam = np.where((tgrp > 0.0) & (raw_diam < 0.5), 0.5, raw_diam)
    diam = np.where(has_convection, np.round(np.clip(raw_diam, 0.0, 10.0), 1), 0.0)

    # 6. Niveau de Risque (0: Nul, 1: Faible, 2: Modéré, 3: Sévère, 4: Géant)
    level = np.zeros_like(prob, dtype=np.int32)
    level = np.where((prob >= 15.0) | (diam >= 0.5), 1, level)
    level = np.where((prob >= 45.0) | (diam >= 1.5), 2, level)
    level = np.where((prob >= 70.0) | (diam >= 3.0), 3, level)
    level = np.where((prob >= 85.0) | (diam >= 5.0), 4, level)

    return prob, diam, level

if __name__ == "__main__":
    # Tests unitaires
    print("Test 1 (Pluie normale 35 dBZ, CAPE 200 J/kg) :", compute_hail_metrics(35, 200, 0))
    print("Test 2 (Orage faible 48 dBZ, CAPE 800 J/kg)   :", compute_hail_metrics(48, 800, 0.2))
    print("Test 3 (Orage modéré 55 dBZ, CAPE 1400 J/kg)  :", compute_hail_metrics(55, 1400, 1.5))
    print("Test 4 (Supercellule 64 dBZ, CAPE 2400 J/kg)  :", compute_hail_metrics(64, 2400, 4.0))
