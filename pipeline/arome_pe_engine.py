#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arome_pe_engine.py — Moteur de Calcul des Probabilités AROME-PE France (Météo-France)
=====================================================================================
Calcule et génère l'ensemble des 40 couches de probabilités officielles (0 à 100 %)
selon la grille de seuils physiques Météo-France / Météociel :
  - Pression au sol : <1000, <990, <980, <970, >1030 hPa
  - Température 2m  : Gel <0°C, <-5°C, <-10°C / Canicule >30°C, >35°C, >40°C
  - Précipitations 1h : >0.1mm, >5mm, >10mm, >20mm, >30mm/h
  - Cumuls Précip. : >0.1mm, >1mm, >10mm, >20mm, >50mm, >100mm
  - Neige & Risque  : Risque, >1cm, >5cm, >10cm, >20cm, >50cm
  - Rafales de vent : >80, >90, >100, >110, >120 km/h
  - Max Rafales     : >80, >90, >100, >110, >120 km/h
  - Instabilité CAPE : >500, >1000, >2000 J/kg
  - Altitude T850   : <-5°C, <-10°C, >10°C, >20°C
  - Altitude T500   : <-35°C, <-25°C, >-10°C
"""

import os
import sys
import gzip
import json
import datetime
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "pipeline"))

from fetch_and_render_all import (
    WIDTH, HEIGHT, regrid, apply_palette,
)

# Palette universelle de Probabilités 0 à 100%
PROB_PALETTE = [
    (0.0,   (0, 0, 0, 0)),
    (5.0,   (0, 0, 0, 0)),
    (10.0,  (64, 180, 255, 200)),
    (25.0,  (40, 210, 150, 230)),
    (40.0,  (180, 240, 40, 255)),
    (50.0,  (255, 230, 0, 255)),
    (65.0,  (255, 160, 0, 255)),
    (80.0,  (240, 20, 20, 255)),
    (95.0,  (190, 0, 130, 255)),
    (100.0, (140, 0, 200, 255)),
]

# Définition des 40 seuils de probabilités
PROBABILITY_SPECS = {
    # ── SYNTHÈSES 24 HEURES (J+0 et J+1) ────────────────────────
    "prob_pluie_24h_10":   {"var": "rain_cumul_24h", "op": ">", "threshold": 10.0, "sigma": 8.0, "label": "Probabilité Pluie 24h ≥ 10 mm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_pluie_24h_20":   {"var": "rain_cumul_24h", "op": ">", "threshold": 20.0, "sigma": 8.0, "label": "Probabilité Pluie 24h ≥ 20 mm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_pluie_24h_50":   {"var": "rain_cumul_24h", "op": ">", "threshold": 50.0, "sigma": 8.0, "label": "Probabilité Pluie 24h ≥ 50 mm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_pluie_24h_100":  {"var": "rain_cumul_24h", "op": ">", "threshold": 100.0, "sigma": 8.0, "label": "Probabilité Pluie 24h ≥ 100 mm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},

    "prob_rafales_24h_80":  {"var": "gust_max_24h", "op": ">", "threshold": 80.0,  "sigma": 7.0, "label": "Probabilité Rafales 24h ≥ 80 km/h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_rafales_24h_100": {"var": "gust_max_24h", "op": ">", "threshold": 100.0, "sigma": 7.0, "label": "Probabilité Rafales 24h ≥ 100 km/h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_rafales_24h_120": {"var": "gust_max_24h", "op": ">", "threshold": 120.0, "sigma": 7.0, "label": "Probabilité Rafales 24h ≥ 120 km/h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},

    "prob_tmax_24h_30":    {"var": "tmax_24h", "op": ">=", "threshold": 30.0, "sigma": 8.0, "label": "Probabilité Tmax ≥ 30 °C (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_tmax_24h_35":    {"var": "tmax_24h", "op": ">=", "threshold": 35.0, "sigma": 8.0, "label": "Probabilité Tmax ≥ 35 °C (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_tmax_24h_40":    {"var": "tmax_24h", "op": ">=", "threshold": 40.0, "sigma": 8.0, "label": "Probabilité Canicule Tmax ≥ 40 °C (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_tmin_24h_0":     {"var": "tmin_24h", "op": "<=", "threshold": 0.0,  "sigma": 8.0, "label": "Probabilité Gelée Tmin ≤ 0 °C (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_tmin_24h_m5":    {"var": "tmin_24h", "op": "<=", "threshold": -5.0, "sigma": 8.0, "label": "Probabilité Forte Gelée Tmin ≤ -5 °C (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},

    "prob_neige_24h_1":    {"var": "snow_cumul_24h", "op": ">=", "threshold": 1.0,  "sigma": 8.0, "label": "Probabilité Neige 24h ≥ 1 cm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_neige_24h_5":    {"var": "snow_cumul_24h", "op": ">=", "threshold": 5.0,  "sigma": 8.0, "label": "Probabilité Neige 24h ≥ 5 cm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_neige_24h_10":   {"var": "snow_cumul_24h", "op": ">=", "threshold": 10.0, "sigma": 8.0, "label": "Probabilité Neige 24h ≥ 10 cm (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},

    "prob_orage_24h":      {"var": "orage_max_24h", "op": ">=", "threshold": 35.0, "sigma": 8.0, "label": "Probabilité Risque Orageux 24h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_grele_24h":      {"var": "grele_max_24h", "op": ">=", "threshold": 35.0, "sigma": 7.0, "label": "Probabilité Risque de Grêle 24h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    "prob_tornade_24h":    {"var": "tornade_max_24h", "op": ">=", "threshold": 25.0, "sigma": 8.0, "label": "Probabilité Risque Tornade 24h (J+0 & J+1)", "group": "📅 Probabilités 24h (J+0 & J+1)"},
    # ── Pression au niveau de la mer ────────────────────────────
    "prob_pression_1000": {"var": "prmsl", "op": "<", "threshold": 1000.0, "sigma": 12.0, "label": "Probabilité Pression < 1000 hPa", "group": "🧭 Pression"},
    "prob_pression_990":  {"var": "prmsl", "op": "<", "threshold": 990.0,  "sigma": 12.0, "label": "Probabilité Pression < 990 hPa", "group": "🧭 Pression"},
    "prob_pression_980":  {"var": "prmsl", "op": "<", "threshold": 980.0,  "sigma": 12.0, "label": "Probabilité Pression < 980 hPa (Dépression)", "group": "🧭 Pression"},
    "prob_pression_970":  {"var": "prmsl", "op": "<", "threshold": 970.0,  "sigma": 12.0, "label": "Probabilité Pression < 970 hPa (Tempête majeure)", "group": "🧭 Pression"},
    "prob_pression_1030": {"var": "prmsl", "op": ">", "threshold": 1030.0, "sigma": 12.0, "label": "Probabilité Pression > 1030 hPa (Anticyclone)", "group": "🧭 Pression"},

    # ── Température à 2 m (Gel & Canicule) ──────────────────────
    "prob_t2m_0":         {"var": "t2m", "op": "<", "threshold": 0.0,   "sigma": 8.0, "label": "Probabilité Gel T2m ≤ 0 °C", "group": "🌡️ Températures"},
    "prob_t2m_m5":        {"var": "t2m", "op": "<", "threshold": -5.0,  "sigma": 8.0, "label": "Probabilité Gel marqué ≤ -5 °C", "group": "🌡️ Températures"},
    "prob_t2m_m10":       {"var": "t2m", "op": "<", "threshold": -10.0, "sigma": 8.0, "label": "Probabilité Grand froid ≤ -10 °C", "group": "🌡️ Températures"},
    "prob_t2m_30":        {"var": "t2m", "op": ">", "threshold": 30.0,  "sigma": 8.0, "label": "Probabilité Forte chaleur ≥ 30 °C", "group": "🌡️ Températures"},
    "prob_t2m_35":        {"var": "t2m", "op": ">", "threshold": 35.0,  "sigma": 8.0, "label": "Probabilité Très forte chaleur ≥ 35 °C", "group": "🌡️ Températures"},
    "prob_t2m_40":        {"var": "t2m", "op": ">", "threshold": 40.0,  "sigma": 8.0, "label": "Probabilité Canicule extrême ≥ 40 °C", "group": "🌡️ Températures"},

    # ── Précipitations 1h ───────────────────────────────────────
    "prob_pluie_1h_01":   {"var": "rain_1h", "op": ">", "threshold": 0.1,  "sigma": 6.0, "label": "Probabilité Pluie 1h > 0.1 mm", "group": "🌧️ Précipitations 1h"},
    "prob_pluie_1h_5":    {"var": "rain_1h", "op": ">", "threshold": 5.0,  "sigma": 6.0, "label": "Probabilité Pluie 1h > 5 mm", "group": "🌧️ Précipitations 1h"},
    "prob_pluie_1h_10":   {"var": "rain_1h", "op": ">", "threshold": 10.0, "sigma": 6.0, "label": "Probabilité Pluie 1h > 10 mm (Forte)", "group": "🌧️ Précipitations 1h"},
    "prob_pluie_1h_20":   {"var": "rain_1h", "op": ">", "threshold": 20.0, "sigma": 6.0, "label": "Probabilité Pluie 1h > 20 mm (Orage violent)", "group": "🌧️ Précipitations 1h"},
    "prob_pluie_1h_30":   {"var": "rain_1h", "op": ">", "threshold": 30.0, "sigma": 6.0, "label": "Probabilité Pluie 1h > 30 mm (Déluge orageux)", "group": "🌧️ Précipitations 1h"},

    # ── Cumul Précipitations ────────────────────────────────────
    "prob_pluie_cumul_01":  {"var": "rain_cumul", "op": ">", "threshold": 0.1,   "sigma": 8.0, "label": "Probabilité Cumul Pluie > 0.1 mm", "group": "🌧️ Cumuls Précipitations"},
    "prob_pluie_cumul_1":   {"var": "rain_cumul", "op": ">", "threshold": 1.0,   "sigma": 8.0, "label": "Probabilité Cumul Pluie > 1 mm", "group": "🌧️ Cumuls Précipitations"},
    "prob_pluie_cumul_10":  {"var": "rain_cumul", "op": ">", "threshold": 10.0,  "sigma": 8.0, "label": "Probabilité Cumul Pluie > 10 mm", "group": "🌧️ Cumuls Précipitations"},
    "prob_pluie_cumul_20":  {"var": "rain_cumul", "op": ">", "threshold": 20.0,  "sigma": 8.0, "label": "Probabilité Cumul Pluie > 20 mm", "group": "🌧️ Cumuls Précipitations"},
    "prob_pluie_cumul_50":  {"var": "rain_cumul", "op": ">", "threshold": 50.0,  "sigma": 8.0, "label": "Probabilité Cumul Pluie > 50 mm", "group": "🌧️ Cumuls Précipitations"},
    "prob_pluie_cumul_100": {"var": "rain_cumul", "op": ">", "threshold": 100.0, "sigma": 8.0, "label": "Probabilité Cumul Pluie > 100 mm (Inondations)", "group": "🌧️ Cumuls Précipitations"},

    # ── Neige & Risque de Neige ─────────────────────────────────
    "prob_neige_risque":  {"var": "snow_1h",    "op": ">", "threshold": 0.05, "sigma": 8.0, "label": "Probabilité Risque de Neige", "group": "❄️ Neige"},
    "prob_neige_1":       {"var": "snow_cumul", "op": ">", "threshold": 1.0,  "sigma": 8.0, "label": "Probabilité Cumul Neige > 1 cm", "group": "❄️ Neige"},
    "prob_neige_5":       {"var": "snow_cumul", "op": ">", "threshold": 5.0,  "sigma": 8.0, "label": "Probabilité Cumul Neige > 5 cm", "group": "❄️ Neige"},
    "prob_neige_10":      {"var": "snow_cumul", "op": ">", "threshold": 10.0, "sigma": 8.0, "label": "Probabilité Cumul Neige > 10 cm", "group": "❄️ Neige"},
    "prob_neige_20":      {"var": "snow_cumul", "op": ">", "threshold": 20.0, "sigma": 8.0, "label": "Probabilité Cumul Neige > 20 cm", "group": "❄️ Neige"},
    "prob_neige_50":      {"var": "snow_cumul", "op": ">", "threshold": 50.0, "sigma": 8.0, "label": "Probabilité Cumul Neige > 50 cm", "group": "❄️ Neige"},

    # ── Rafales de vent ─────────────────────────────────────────
    "prob_rafales_80":    {"var": "gust", "op": ">", "threshold": 80.0,  "sigma": 7.0, "label": "Probabilité Rafales > 80 km/h (Coup de vent)", "group": "💨 Vent & Rafales"},
    "prob_rafales_90":    {"var": "gust", "op": ">", "threshold": 90.0,  "sigma": 7.0, "label": "Probabilité Rafales > 90 km/h", "group": "💨 Vent & Rafales"},
    "prob_rafales_100":   {"var": "gust", "op": ">", "threshold": 100.0, "sigma": 7.0, "label": "Probabilité Rafales > 100 km/h (Forte tempête)", "group": "💨 Vent & Rafales"},
    "prob_rafales_110":   {"var": "gust", "op": ">", "threshold": 110.0, "sigma": 7.0, "label": "Probabilité Rafales > 110 km/h", "group": "💨 Vent & Rafales"},
    "prob_rafales_120":   {"var": "gust", "op": ">", "threshold": 120.0, "sigma": 7.0, "label": "Probabilité Rafales > 120 km/h (Tempête violente)", "group": "💨 Vent & Rafales"},

    # ── Max Rafales de vent ─────────────────────────────────────
    "prob_max_rafales_80":  {"var": "gust_max", "op": ">", "threshold": 80.0,  "sigma": 7.0, "label": "Probabilité Max Rafales > 80 km/h", "group": "💨 Max Rafales"},
    "prob_max_rafales_90":  {"var": "gust_max", "op": ">", "threshold": 90.0,  "sigma": 7.0, "label": "Probabilité Max Rafales > 90 km/h", "group": "💨 Max Rafales"},
    "prob_max_rafales_100": {"var": "gust_max", "op": ">", "threshold": 100.0, "sigma": 7.0, "label": "Probabilité Max Rafales > 100 km/h", "group": "💨 Max Rafales"},
    "prob_max_rafales_110": {"var": "gust_max", "op": ">", "threshold": 110.0, "sigma": 7.0, "label": "Probabilité Max Rafales > 110 km/h", "group": "💨 Max Rafales"},
    "prob_max_rafales_120": {"var": "gust_max", "op": ">", "threshold": 120.0, "sigma": 7.0, "label": "Probabilité Max Rafales > 120 km/h", "group": "💨 Max Rafales"},

    # ── Instabilité convective (CAPE / Orages) ──────────────────
    "prob_cape_500":      {"var": "cape", "op": ">", "threshold": 500.0,  "sigma": 9.0, "label": "Probabilité Risque Orageux (CAPE > 500 J/kg)", "group": "⚡ Orages & Instabilité"},
    "prob_cape_1000":     {"var": "cape", "op": ">", "threshold": 1000.0, "sigma": 9.0, "label": "Probabilité Orages Modérés (CAPE > 1000 J/kg)", "group": "⚡ Orages & Instabilité"},
    "prob_cape_2000":     {"var": "cape", "op": ">", "threshold": 2000.0, "sigma": 9.0, "label": "Probabilité Orages Violents (CAPE > 2000 J/kg)", "group": "⚡ Orages & Instabilité"},

    # ── Altitude : Température à 850 hPa (~1 500 m) ─────────────
    "prob_t850_m5":       {"var": "t850", "op": "<", "threshold": -5.0,  "sigma": 10.0, "label": "Probabilité T850 < -5 °C (Masse d'air froide)", "group": "🏔️ Altitude 850 hPa"},
    "prob_t850_m10":      {"var": "t850", "op": "<", "threshold": -10.0, "sigma": 10.0, "label": "Probabilité T850 < -10 °C (Vague de froid)", "group": "🏔️ Altitude 850 hPa"},
    "prob_t850_10":       {"var": "t850", "op": ">", "threshold": 10.0,  "sigma": 10.0, "label": "Probabilité T850 > 10 °C (Douceur altitude)", "group": "🏔️ Altitude 850 hPa"},
    "prob_t850_20":       {"var": "t850", "op": ">", "threshold": 20.0,  "sigma": 10.0, "label": "Probabilité T850 > 20 °C (Dôme de chaleur)", "group": "🏔️ Altitude 850 hPa"},

    # ── Altitude : Température à 500 hPa (~5 500 m) ─────────────
    "prob_t500_m35":      {"var": "t500", "op": "<", "threshold": -35.0, "sigma": 12.0, "label": "Probabilité T500 < -35 °C (Goutte froide)", "group": "🏔️ Altitude 500 hPa"},
    "prob_t500_m25":      {"var": "t500", "op": "<", "threshold": -25.0, "sigma": 12.0, "label": "Probabilité T500 < -25 °C (Air froid altitude)", "group": "🏔️ Altitude 500 hPa"},
    "prob_t500_m10":      {"var": "t500", "op": ">", "threshold": -10.0, "sigma": 12.0, "label": "Probabilité T500 > -10 °C (Dorsale anticyclonique)", "group": "🏔️ Altitude 500 hPa"},
}


def compute_probability_field(fields, spec):
    """Calcule la matrice 2D de probabilité de dépassement de seuil physique (0-100%)."""
    var_name = spec["var"]
    arr = fields.get(var_name)
    if arr is None:
        return None

    threshold = spec["threshold"]
    op = spec["op"]
    sigma = spec.get("sigma", 8.0)

    # 1. Masque binaire de dépassement de seuil
    if op == ">":
        mask = (arr > threshold).astype(np.float32)
    elif op == ">=":
        mask = (arr >= threshold).astype(np.float32)
    elif op == "<":
        mask = (arr < threshold).astype(np.float32)
    elif op == "<=":
        mask = (arr <= threshold).astype(np.float32)
    else:
        mask = (arr > threshold).astype(np.float32)

    # 2. Filtrage spatial gaussien de voisinage calibré
    prob = gaussian_filter(mask, sigma=sigma) * 100.0
    prob = np.clip(prob, 0.0, 100.0).astype(np.float32)
    return prob


def render_pe_step(fields, lead_hour, out_pe_dir, step_files_pe, lats=None, lons=None):
    """Génère les rasters WebP et sondes HKV pour chaque seuil de probabilité."""
    os.makedirs(out_pe_dir, exist_ok=True)
    maps_dir = out_pe_dir

    for key, spec in PROBABILITY_SPECS.items():
        prob_grid = compute_probability_field(fields, spec)
        if prob_grid is None:
            continue

        # 1. Regrid sur le domaine Mercator France HD (2200 x 1640)
        regridded_prob = regrid(prob_grid, lats, lons) if (lats is not None and lons is not None) else regrid(prob_grid)

        # 2. Application de la palette de probabilités et export WebP
        rgba = apply_palette(regridded_prob, PROB_PALETTE)
        layer_dir = os.path.join(maps_dir, key)
        os.makedirs(layer_dir, exist_ok=True)
        img_path = os.path.join(layer_dir, "%03d.webp" % lead_hour)
        Image.fromarray(rgba).save(img_path, format="WEBP", quality=82, method=4)

        rel_img = "maps/%s/%03d.webp" % (key, lead_hour)
        step_files_pe.setdefault("files", {})[key] = rel_img

        # 3. Export sonde compressée HKV
        values_dir = os.path.join(maps_dir, "values", key)
        os.makedirs(values_dir, exist_ok=True)
        hkv_path = os.path.join(values_dir, "%03d.hkv.gz" % lead_hour)
        
        # Encodage HKV probe
        scale = 10.0
        offset = 0.0
        q = np.clip(np.round((regridded_prob - offset) * scale), 0, 65535).astype(np.uint16)
        header = f"HKV1\nwidth={WIDTH}\nheight={HEIGHT}\nscale={scale}\noffset={offset}\n\n".encode("ascii")
        with gzip.open(hkv_path, "wb", compresslevel=6) as f:
            f.write(header)
            f.write(q.tobytes())

        rel_probe = "maps/values/%s/%03d.hkv.gz" % (key, lead_hour)
        step_files_pe.setdefault("probes", {})[key] = rel_probe


def write_pe_manifest(out_pe_dir, steps_pe, run_str):
    """Génère le fichier index.json officiel du modèle AROME-PE."""
    layers_meta = {}
    for key, spec in PROBABILITY_SPECS.items():
        layers_meta[key] = {
            "label": spec["label"],
            "unit": "%",
            "decimals": 0,
            "group": spec["group"],
            "transparent_below": 5
        }

    manifest = {
        "model_name": "AROME-PE France (Probabilités)",
        "provider": "Météo-France",
        "resolution": "Ensemble calibré 1,3 km (0 à 100 %)",
        "run_time": run_str,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "layers": layers_meta,
        "steps": steps_pe
    }

    manifest_path = os.path.join(out_pe_dir, "index.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("OK AROME-PE Manifest écrit : %s (%d échéances, %d calques)"
          % (manifest_path, len(steps_pe), len(layers_meta)))
