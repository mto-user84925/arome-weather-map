# -*- coding: utf-8 -*-
"""
arome_render.py — Conventions de rendu AROME HD (module Grêle)
================================================================
Module de rendu dédié au pipeline `arome_open_data_remote.py` (0,025° +
indices IPO/IPG/IPT). Séparé de `fetch_and_render_all.py` du dépôt
(pipeline multi-modèles) pour éviter toute collision.

Exports : PALETTES, BOUNDS, WIDTH, HEIGHT, regrid, apply_palette,
          DISCRETE_LAYERS, write_manifest.

Fonctionne dans deux environnements :
  - dépôt GitHub (palettes_data.py + domains.py dans pipeline/)
  - local HARNESS (palettes_data.py + domains.py dans gfs-weather-map/pipeline/)
"""
import os
import sys
import json
import datetime

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))          # .../pipeline
ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
try:
    from palettes_data import PALETTES        # noqa: E402  (source unique)
    from domains import FRANCE                # noqa: E402  (grille Mercator 2200×1640)
except ImportError:
    sys.path.insert(0, os.path.join(ROOT, "gfs-weather-map", "pipeline"))
    from palettes_data import PALETTES        # noqa: E402
    from domains import FRANCE                # noqa: E402

WIDTH = FRANCE.width                          # 2200
HEIGHT = FRANCE.height                        # 1640
BOUNDS = FRANCE.bounds                        # {south, west, north, east, projection}

# Couches qualitatives rendues en BANDES DISCRÈTES : chaque classe reçoit la
# couleur PLEINE de son seuil bas → couleurs IDENTIQUES aux légendes
# (LAYER_LEGENDS dans grele.html). Les champs physiques restent en dégradé.
DISCRETE_LAYERS = {"ipo", "ipg", "ipt", "instabilite",
                   "orages_simules", "rafales_convectives"}

# Métadonnées des couches pour le manifeste index.json
# (label, unité, décimales, groupe optionnel)
LAYER_META = {
    "temperature": ("Temperature a 2 m", "degC", 1),
    "temperature_ressentie": ("Temperature ressentie", "degC", 1),
    "point_rosee": ("Point de rosee a 2 m", "degC", 1),
    "humidex": ("Indice Humidex", "", 1),
    "humidite": ("Humidite relative a 2 m", "%", 1),
    "pluie_1h": ("Pluie horaire", "mm", 1),
    "pluie_cumul": ("Precipitations cumulees", "mm", 1),
    "neige": ("Chutes de neige", "cm/h", 1),
    "neige_au_sol": ("Epaisseur neige au sol", "cm", 1),
    "equivalent_eau_neige": ("Cumul neigeux equiv. eau", "mm", 1),
    "graupel": ("Graupel / Gresil", "mm", 1),
    "nebulosite": ("Nebulosite totale", "%", 1),
    "nuages_bas": ("Couverture nuages bas", "%", 1),
    "nuages_moyens": ("Couverture nuages moyens", "%", 1),
    "nuages_eleves": ("Couverture nuages eleves", "%", 1),
    "vent": ("Vent moyen a 10 m", "km/h", 1),
    "rafales": ("Rafales maximales", "km/h", 1),
    "rafales_cumul": ("Rafales maximales cumulees", "km/h", 1),
    "pression": ("Pression niveau mer", "hPa", 1),
    "pression_surface": ("Pression au sol", "hPa", 1),
    "mucape": ("Instabilite convective (MUCAPE)", "J/kg", 1),
    "reflectivite": ("Reflectivite radar Doppler", "dBZ", 1),
    "ipo": ("⚡ Indice de Potentiel Orageux (IPO /100)", "", 0,
            "⚡ Orages, Grêle & Tornades"),
    "ipg": ("🌩️ Indice de Potentiel Grêle (IPG /100)", "", 0,
            "⚡ Orages, Grêle & Tornades"),
    "ipt": ("🌪️ Indice de Potentiel Tornadique (IPT /100)", "", 0,
            "⚡ Orages, Grêle & Tornades"),
    "instabilite": ("⚡ Instabilité convective (MUCAPE)", "J/kg", 0,
                    "⚡ Orages, Grêle & Tornades"),
    "orages_simules": ("⛈️ Orages simulés (réflectivité)", "dBZ", 0,
                       "⚡ Orages, Grêle & Tornades"),
    "rafales_convectives": ("💨 Rafales convectives", "km/h", 0,
                            "⚡ Orages, Grêle & Tornades"),
}


def regrid(arr, lat, lon):
    """Ré-échantillonne un champ natif (lat, lon vecteurs 1D réguliers) sur la
    grille Mercator France 2200×1640 (interpolation bilinéaire, NaN hors
    domaine)."""
    return FRANCE.regrid(arr, lat, lon)


def apply_palette(data, palette, discrete=False):
    """Applique une palette (liste de (seuil, rgba)) → RGBA uint8.

    discrete=True : bandes PLEINES — chaque classe [seuil_i, seuil_{i+1})
    reçoit la couleur de son seuil bas (identique aux légendes).
    discrete=False : dégradé linéaire continu entre les seuils.
    NaN → transparent (alpha 0).
    """
    data = np.asarray(data, dtype=np.float32)
    vs = np.array([s[0] for s in palette], dtype=np.float32)
    cs = np.array([list(s[1]) for s in palette], dtype=np.float32)
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    valid = np.isfinite(data)
    if not np.any(valid):
        return rgba
    d = data[valid]
    if discrete:
        idx = np.clip(np.searchsorted(vs, d, side="right") - 1, 0, len(vs) - 1)
        rgba[valid] = cs[idx].astype(np.uint8)
    else:
        idx = np.clip(np.searchsorted(vs, d, side="right") - 1, 0, len(vs) - 2)
        t = np.clip((d - vs[idx]) / np.maximum(vs[idx + 1] - vs[idx], 1e-6),
                    0.0, 1.0)
        for c in range(4):
            rgba[valid, c] = np.clip(
                cs[idx, c] + t * (cs[idx + 1, c] - cs[idx, c]), 0, 255
            ).astype(np.uint8)
    return rgba


# ── Places (communes.json) ──────────────────────────────────────────────────
def write_places(out_dir):
    """Génère maps/communes.json : communes du domaine France (tri population)."""
    rows = None
    for cand in (os.path.join(ROOT, "config", "communes-compact.json"),
                 os.path.join(ROOT, "gfs-weather-map", "config",
                              "communes-compact.json")):
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                rows = json.load(f)
            break
    if rows is None:
        return False
    out = []
    w, e = BOUNDS["west"], BOUNDS["east"]
    s, n = BOUNDS["south"], BOUNDS["north"]
    for r in rows:
        try:
            lat, lon = float(r[5]), float(r[6])
            pop = int(r[4])
        except (IndexError, TypeError, ValueError):
            continue
        if w <= lon <= e and s <= lat <= n:
            out.append([r[1], pop, lat, lon])
    seen = set()
    unique = []
    out.sort(key=lambda p: -p[1])
    for p in out:
        key = p[0].lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "communes.json"), "w", encoding="utf-8") as f:
        json.dump({"places": unique}, f, ensure_ascii=False)
    return True


# ── Manifeste exact ─────────────────────────────────────────────────────────
def write_manifest(out_dir, steps, meta):
    """Manifeste index.json : ne référence QUE les couches réellement rendues.
    out_dir : output/arome/maps ; meta : {name, provider, resolution, run_time}."""
    layers_info = {}
    for step in steps:
        for layer in (step.get("files") or {}):
            if layer in LAYER_META and layer not in layers_info:
                label, unit, dec = LAYER_META[layer][:3]
                info = {"label": label, "unit": unit, "decimals": dec}
                if len(LAYER_META[layer]) > 3 and LAYER_META[layer][3]:
                    info["group"] = LAYER_META[layer][3]
                layers_info[layer] = info
    m = {
        "schema_version": 6,
        "status": "ok",
        "model_name": meta["name"],
        "provider": meta["provider"],
        "resolution": meta["resolution"],
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "run_time": meta["run_time"],
        "bounds": BOUNDS,
        "overlay": "maps/frontieres.svg",
        "places": "maps/communes.json",
        "layers": layers_info,
        "steps": steps,
    }
    try:
        write_places(out_dir)
    except Exception as e:
        print("  [write_manifest] communes.json non écrit (%s)" % e)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
    return m
