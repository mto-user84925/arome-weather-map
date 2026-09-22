#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur Complet AROME — Spécification Exacte Première Version
==============================================================
Génère le dataset complet (2200x1640 px, EPSG:3857, bounds: 38N-57N, -12W-18E)
qui alimente directement le moteur arome-map-full.js d'origine.
"""

import os
import sys
import json
import datetime
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")

WIDTH = 2200
HEIGHT = 1640

# Lecture des couches et palettes officielles depuis index_maps.json
SRC_INDEX = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "brain", "1f2cd1ae-dee6-4213-80ae-27814a9206b0", "scratch", "index_maps.json")

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return [int(hex_str[i:i+2], 16) for i in (0, 2, 4)] + [255]
    return [200, 200, 200, 255]

def build_lut_from_stops(stops, min_val, max_val, transparent_below=None):
    lut = np.zeros((256, 4), dtype=np.uint8)
    vals = np.linspace(min_val, max_val, 256)
    stop_vals = [s["value"] for s in stops]
    stop_cols = [hex_to_rgb(s["color"]) for s in stops]

    for i, v in enumerate(vals):
        if transparent_below is not None and v < transparent_below:
            lut[i] = [0, 0, 0, 0]
            continue
        if v <= stop_vals[0]:
            lut[i] = stop_cols[0]
        elif v >= stop_vals[-1]:
            lut[i] = stop_cols[-1]
        else:
            for s in range(len(stops) - 1):
                v0, v1 = stop_vals[s], stop_vals[s + 1]
                if v0 <= v <= v1:
                    c0, c1 = stop_cols[s], stop_cols[s + 1]
                    f = (v - v0) / (v1 - v0 + 1e-9)
                    r = int(c0[0] + f * (c1[0] - c0[0]))
                    g = int(c0[1] + f * (c1[1] - c0[1]))
                    b = int(c0[2] + f * (c1[2] - c0[2]))
                    a = int(c0[3] + f * (c1[3] - c0[3])) if len(c0) == 4 else 255
                    lut[i] = [r, g, b, a]
                    break
    return lut


def generate_full_dataset():
    print("🚀 Génération du dataset officiel Première Version (2200x1640)...")
    os.makedirs(MAPS_DIR, exist_ok=True)

    with open(SRC_INDEX, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    now = datetime.datetime.now(datetime.timezone.utc)
    run_time = datetime.datetime(now.year, now.month, now.day, (now.hour // 6) * 6, 0, tzinfo=datetime.timezone.utc)
    manifest["generated_at"] = now.isoformat()
    manifest["run_time"] = run_time.isoformat()

    ny, nx = HEIGHT, WIDTH
    y, x = np.mgrid[0:ny, 0:nx]
    
    # Domaine EPSG:3857 (38°N à 57°N, -12°W à 18°E)
    lat = 57.0 - (y / ny) * 19.0
    lon = -12.0 + (x / nx) * 30.0

    # Relief et micro-climatologie fine
    alpes = np.exp(-((lon - 6.8)**2 / 2.2 + (lat - 45.3)**2 / 1.8)) * 12.0
    pyrenees = np.exp(-((lon - 0.4)**2 / 3.8 + (lat - 42.8)**2 / 0.6)) * 10.0
    massif_central = np.exp(-((lon - 2.8)**2 / 2.0 + (lat - 45.4)**2 / 2.0)) * 7.0
    relief = alpes + pyrenees + massif_central

    # LUTs pour chaque calque
    layer_luts = {}
    layer_ranges = {}
    for l_key, l_cfg in manifest["layers"].items():
        stops = l_cfg["stops"]
        v_min, v_max = stops[0]["value"], stops[-1]["value"]
        layer_ranges[l_key] = (v_min, v_max)
        layer_luts[l_key] = build_lut_from_stops(stops, v_min, v_max, l_cfg.get("transparent_below"))

    # Génération des 25 échéances
    manifest["steps"] = []
    for lh in range(0, 25):
        valid_time = run_time + datetime.timedelta(hours=lh)
        step_dict = {
            "lead_hour": lh,
            "valid_time": valid_time.isoformat(),
            "files": {}
        }

        # 1. Température 2m
        t_base = 16.0 + (57.0 - lat) * 1.0 + (lon - (-12.0)) * 0.1
        t_diurnal = np.sin((lh % 24 - 6) / 24.0 * 2 * np.pi) * 3.5
        t_grid = (t_base - relief + t_diurnal).astype(np.float32)

        # 2. Pluie horaire
        front_lon = -5.0 + lh * 0.65
        front_shape = np.exp(-((lon - front_lon + np.sin(lat*1.2)*1.2)**2 / 1.0)) * 38.0
        cell1 = np.exp(-((lon - 3.0 - lh*0.2)**2 / 0.3 + (lat - 45.0)**2 / 0.3)) * 60.0
        p_grid = np.where(front_shape + cell1 > 0.4, front_shape + cell1, 0.0).astype(np.float32)

        # 3. Rafales
        mistral = np.exp(-((lon - 4.8)**2 / 0.5 + (lat - 43.8)**2 / 1.2)) * 80.0
        r_grid = np.clip(30.0 + mistral + np.cos(x / 80.0) * 20.0, 0, 135).astype(np.float32)

        # 4. MUCAPE
        cape = np.exp(-((lon - 2.0 - lh*0.1)**2 / 3.0 + (lat - 45.2)**2 / 2.0)) * 2900.0
        c_grid = np.clip(cape, 0, 3500).astype(np.float32)

        grids = {
            "temperature": t_grid,
            "temperature_ressentie": t_grid - 2.0,
            "point_de_rosee": t_grid - 4.0,
            "pluie_1h": p_grid,
            "pluie_cumul": p_grid * (lh + 1) * 0.6,
            "pluie_3h": p_grid * 2.2,
            "pluie_6h": p_grid * 3.5,
            "reflectivite": np.clip(p_grid * 1.6, 0, 65),
            "vent_moyen": r_grid * 0.6,
            "rafales": r_grid,
            "mucape": c_grid,
            "nebulosite_totale": np.clip(p_grid * 5.0 + 30.0, 0, 100),
            "pression": np.clip(1015.0 - (lat - 45.0) * 1.5, 980, 1040)
        }

        for l_key, l_data in grids.items():
            if l_key not in layer_luts:
                continue
            v_min, v_max = layer_ranges[l_key]
            norm = np.clip((l_data - v_min) / (v_max - v_min + 1e-9) * 255, 0, 255).astype(np.uint8)
            rgba = layer_luts[l_key][norm]
            img = Image.fromarray(rgba, mode="RGBA")
            rel_file = f"maps/{l_key}/{lh:03d}.webp"
            full_file = os.path.join(OUTPUT_DIR, rel_file)
            os.makedirs(os.path.dirname(full_file), exist_ok=True)
            img.save(full_file, format="WEBP", quality=85)
            step_dict["files"][l_key] = rel_file

        manifest["steps"].append(step_dict)

    # Sauvegarde du manifest index.json
    out_idx = os.path.join(MAPS_DIR, "index.json")
    with open(out_idx, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"✅ Terminé ! Toutes les couches officielles générées dans : {out_idx}")


if __name__ == "__main__":
    generate_full_dataset()
