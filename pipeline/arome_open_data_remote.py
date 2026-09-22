#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROGRAMME NEUF v3 — Tuiles AROME HD + Prévisions par commune
==============================================================
  Données   : paquets GRIB2 AROME 0,025° (open data Météo-France, data.gouv.fr),
              SP1+SP2 par chunks de 7 h (00H06H … 49H51H), échéances horaires 0→51 h
  Décodage  : eccodes (contrôle total des champs)
  Projection: Mercator (2200×1640) — France non étirée
  Couleurs  : palettes météociel (vives)
  Communes  : extraction par interpolation bilinéaire à la position exacte
              de chaque commune (34 746) + fichiers binaires int16/zlib
              par département (beaucoup plus léger que le JSON de référence)

v3 (bascule 0,025°) :
  - Les paquets 0,01° ne publient plus les champs convectifs (réflectivité,
    graupel, pluie, nuages, rafales) → passage au produit 0,025° complet.
  - Réflectivité simulée recalculée par Marshall-Palmer (Z=200·R^1,6) à
    partir de la pluie horaire (champ direct 16.193 plus publié).
  - Cisaillement 10→100 m estimé depuis les rafales (proxy, vent 100 m
    plus publié).

Corrections apportées vs v1 :
  - tirf/tsnowp/tgrp sont des CUMULS depuis le début du run
    → valeurs horaires = cumul(H+n) − cumul(H+n−1)
  - Altitude réelle (SP2 H+0, shortName 'h') → pression MSL correcte
  - Neige au sol = cumul de neige fraîche (si10 n'existe pas dans les paquets)
  - Cisaillement vertical estimé depuis les rafales → type d'orage affiné
"""

import os
import re
import sys
import zlib
import struct
import shutil
import tempfile
import datetime
import warnings

import requests
import numpy as np
from PIL import Image

warnings.filterwarnings("ignore")

# Racine du dépôt : le script vit soit à la racine (poste local HARNESS),
# soit dans pipeline/ (dépôt GitHub arome-weather-map) — on détecte.
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_HERE, "config", "communes-compact.json")):
    BASE_DIR = _HERE                 # local : HARNESS/
else:
    BASE_DIR = os.path.dirname(_HERE)  # GitHub : racine du dépôt
# Répertoire de sortie : par défaut l'output consommé par l'interface locale
# (local_test_grele/output) — surchargeable via la variable AROME_OUT_DIR
# (utilisée par le workflow GitHub : output/ du dépôt).
OUT_BASE = os.environ.get("AROME_OUT_DIR",
                          os.path.join(BASE_DIR, "local_test_grele", "output"))
sys.path.insert(0, os.path.join(BASE_DIR, "pipeline"))
from arome_render import (  # noqa: E402
    PALETTES, BOUNDS, WIDTH, HEIGHT, regrid, apply_palette, DISCRETE_LAYERS,
)

# ── Constantes ──────────────────────────────────────────────────────────────
# Source : AROME 0,025° open data (paquets SP1+SP2 par chunks de 7 h).
# NB : la réflectivité directe du modèle n'est plus publiée en open data ;
# elle est recalculée par Marshall-Palmer (Z=200·R^1,6) dans compute_fields.
GRIB_BASE = ("https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{run}/arome/0025/"
             "{pkg}/arome__0025__{pkg}__{chunk}__{run}.grib2")
GRIB_PKGS = ["SP1", "SP2"]
# Chunks de 7 h couvrant 0→51 h (00H06H, 07H12H, …, 43H48H, 49H51H)
CHUNKS = [(0, 6), (7, 12), (13, 18), (19, 24), (25, 30), (31, 36),
          (37, 42), (43, 48), (49, 51)]
DATASET_API = ("https://www.data.gouv.fr/api/1/datasets/"
               "paquets-arome-resolution-0-025deg/")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Grille native AROME 0,025° (regular_ll, point 0 en haut à gauche)
NI, NJ = 1121, 717
LAT0, LON0, STEP = 55.4, -12.0, 0.025


def _chunk_name(start, end):
    return "%02dH%02dH" % (start, end)


def chunk_for_lead(lead):
    for s, e in CHUNKS:
        if s <= lead <= e:
            return s, e
    return None


# ── Synthèses 24 h J0 / J+1 ─────────────────────────────────────────────────
# Couches convectives synthétisées : max sur la journée locale (Paris).
SYNTH_LAYER_FIELDS = {
    "ipo": "ipo",
    "ipg": "ipg",
    "ipt": "ipt",
    "instabilite": "instabilite",
    "orages_simules": "orages_simules",
    "rafales_convectives": "wind_gust_kmh",
}

try:
    from zoneinfo import ZoneInfo
    TZ_PARIS = ZoneInfo("Europe/Paris")
except Exception:
    TZ_PARIS = datetime.timezone(datetime.timedelta(hours=2))  # repli été


def synth_window(run_dt, lead):
    """Jour local (Paris) de la validité : 'j0' (jour du run), 'j1' (lendemain)
    ou None (au-delà)."""
    vt = run_dt + datetime.timedelta(hours=lead)
    try:
        local = vt.astimezone(TZ_PARIS)
        run_local = run_dt.astimezone(TZ_PARIS)
    except Exception:
        local, run_local = vt, run_dt
    delta = (local.date() - run_local.date()).days
    if delta == 0:
        return "j0"
    if delta == 1:
        return "j1"
    return None


def update_synth(synth, fields, run_dt, lead):
    """Met à jour le maximum glissant des couches convectives pour la fenêtre
    j0/j1 de l'échéance courante (grille native, régridée une seule fois à la
    fin)."""
    win = synth_window(run_dt, lead)
    if win is None:
        return
    for layer, fname in SYNTH_LAYER_FIELDS.items():
        arr = fields.get(fname)
        if arr is None:
            continue
        a = np.asarray(arr, dtype=np.float32)
        cur = synth[win].get(layer)
        synth[win][layer] = a if cur is None else np.fmax(cur, a)


def save_syntheses(synth, out_dir):
    """Écrit maps/{layer}_24h_{j0|j1}.webp (max de la journée, bandes
    discrètes pour les indices)."""
    lats = LAT0 - np.arange(NJ) * STEP
    lons = LON0 + np.arange(NI) * STEP
    for win in ("j0", "j1"):
        for layer, arr in synth[win].items():
            try:
                data = regrid(arr, lats, lons)
            except Exception as e:
                print("  [synth %s %s] regrid: %s" % (layer, win, e))
                continue
            rgba = apply_palette(data, PALETTES.get(layer, PALETTES["temperature"]),
                                 discrete=(layer in DISCRETE_LAYERS))
            dst = os.path.join(out_dir, "%s_24h_%s.webp" % (layer, win))
            Image.fromarray(rgba, "RGBA").save(dst, format="WEBP",
                                               quality=85, method=4)
    print("  Synthèses 24h J0/J+1 écrites (max par couche)")


def latest_run():
    """Trouve le run AROME le plus récent disponible et vérifie sa disponibilité S3."""
    runs = set()
    try:
        r = requests.get(DATASET_API, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            for res in r.json().get("resources", []):
                m = re.search(r"__(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\.grib2",
                              res.get("title", ""))
                if m:
                    runs.add(m.group(1))
    except Exception:
        pass

    if not runs:
        now = datetime.datetime.now(datetime.timezone.utc)
        for delta_h in range(0, 24, 3):
            cand_dt = (now - datetime.timedelta(hours=delta_h))
            cand_h = (cand_dt.hour // 3) * 3
            cand = cand_dt.replace(hour=cand_h, minute=0, second=0, microsecond=0)
            runs.add(cand.strftime("%Y-%m-%dT%H:00:00Z"))

    sorted_runs = sorted(runs, reverse=True)
    for run_cand in sorted_runs:
        test_url = GRIB_BASE.format(run=run_cand, pkg="SP1",
                                    chunk=_chunk_name(*CHUNKS[0]))
        try:
            resp = requests.head(test_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                return run_cand
        except Exception:
            pass
    return sorted_runs[0]


def available_leads(run_str, max_hours=51):
    """Échéances 0→51 h si le premier chunk SP1 est disponible sur le bucket S3."""
    url = GRIB_BASE.format(run=run_str, pkg="SP1", chunk=_chunk_name(*CHUNKS[0]))
    try:
        r = requests.head(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print("  WARNING: chunk %s indisponible pour %s" % (_chunk_name(*CHUNKS[0]), run_str))
            return []
    except Exception:
        return []
    return list(range(0, min(52, max_hours + 1)))


def download_chunk(run_str, start, end, tmpdir):
    """Télécharge SP1+SP2 d'un chunk (7 échéances)."""
    chunk = _chunk_name(start, end)
    paths = []
    for pkg in GRIB_PKGS:
        url = GRIB_BASE.format(run=run_str, pkg=pkg, chunk=chunk)
        dst = os.path.join(tmpdir, "%s_%s.grib2" % (pkg, chunk))
        try:
            r = requests.get(url, headers=HEADERS, timeout=600)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(dst, "wb") as f:
                    f.write(r.content)
                paths.append(dst)
        except Exception:
            pass
    return paths


def read_grib(path, run_str=None, lead=None):
    """Lit un fichier GRIB2 (chunk 7 h) avec eccodes → dict {clé: array 2D (NJ, NI)}.

    Seuls les messages dont la validité == run + lead heures sont conservés
    (un chunk contient 7 échéances horaires).

    Clés produites (paquets SP1/SP2 0,025°) :
      SP1 : t2m, r2, u10, v10, efg10, nfg10, tgrp, tirf, tsnowp
      SP2 : cape, sp, lcc, mcc, hcc, h (altitude)
    NB : la réflectivité directe n'est plus publiée — proxy Marshall-Palmer
    calculé dans compute_fields à partir de la pluie horaire.
    """
    from eccodes import codes_grib_new_from_file, codes_get, codes_get_array, codes_release
    import datetime as _dt

    expected = None
    if run_str and lead is not None:
        run_dt = _dt.datetime.fromisoformat(run_str.replace("Z", "+00:00"))
        expected = run_dt + _dt.timedelta(hours=lead)

    out = {}
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                if expected is not None:
                    vdate = int(codes_get(gid, "validityDate"))
                    vtime = int(codes_get(gid, "validityTime"))
                    vd = _dt.datetime(vdate // 10000, (vdate // 100) % 100,
                                      vdate % 100, vtime // 100, vtime % 100,
                                      tzinfo=_dt.timezone.utc)
                    if vd != expected:
                        continue
                short = str(codes_get(gid, "shortName"))
                disc = int(codes_get(gid, "discipline"))
                cat = int(codes_get(gid, "parameterCategory"))
                num = int(codes_get(gid, "parameterNumber"))
                level = int(codes_get(gid, "level"))
                arr = np.asarray(codes_get_array(gid, "values"),
                                 dtype=np.float64)
                # Grille : le premier point est en haut à gauche (lat LAT0)
                arr = arr.reshape(NJ, NI)
                if short == "2t":
                    out["t2m"] = arr
                elif short == "2r":
                    out["r2"] = arr
                elif short == "10u":
                    out["u10"] = arr
                elif short == "10v":
                    out["v10"] = arr
                elif short == "max_10efg":
                    out["efg10"] = arr
                elif short == "max_10nfg":
                    out["nfg10"] = arr
                elif short == "CAPE_INS":
                    out["cape"] = arr
                elif short == "tgrp":
                    out["tgrp"] = arr
                elif short == "tirf":
                    out["tirf"] = arr
                elif short == "tsnowp":
                    out["tsnowp"] = arr
                elif short == "sp":
                    out["sp"] = arr
                elif short == "lcc":
                    out["lcc"] = arr
                elif short == "mcc":
                    out["mcc"] = arr
                elif short == "hcc":
                    out["hcc"] = arr
                elif short == "h":
                    out["h"] = arr
            except Exception:
                pass
            codes_release(gid)
    return out


def _clean(arr, missing=9999.0):
    arr = np.asarray(arr, dtype=np.float64)
    arr = np.where((arr >= missing - 1.0) | ~np.isfinite(arr), np.nan, arr)
    return arr


def _clean_sp(arr):
    """La pression surface est en Pa (~100 000) : le seuil 'missing' GRIB
    (9999) ne s'applique pas — on filtre seulement les valeurs aberrantes."""
    arr = np.asarray(arr, dtype=np.float64)
    return np.where((arr < 40000.0) | (arr > 110000.0) | ~np.isfinite(arr),
                    np.nan, arr)


# ── Calculs physiques (grille native) ───────────────────────────────────────
def compute_fields(raw, altitude, previous, lead_hour):
    """Calcule tous les champs sur la grille native. Retourne
    (fields: dict nom → array 2D, state: dict cumuls pour l'échéance suivante)."""
    shape = (NJ, NI)

    def get(name, clip=None, scale=1.0, offset=0.0):
        arr = raw.get(name)
        if arr is None:
            return np.full(shape, np.nan)
        arr = _clean(arr) * scale + offset
        if clip:
            arr = np.clip(arr, *clip)
        return arr

    t2m = get("t2m", scale=1.0, offset=-273.15)          # °C
    r2 = np.clip(get("r2"), 0, 100)                       # %
    u10 = get("u10")
    v10 = get("v10")
    efg_u = get("efg10")
    efg_v = get("nfg10")
    cape = np.maximum(get("cape"), 0.0)
    # Réflectivité : calculée après la pluie horaire (proxy Marshall-Palmer),
    # car le champ direct du modèle n'est plus publié en open data.
    refl = np.full(shape, np.nan)
    sp = _clean_sp(raw.get("sp")) * (1.0 / 100.0)         # hPa
    lcc = np.clip(get("lcc"), 0, 100)
    mcc = np.clip(get("mcc"), 0, 100)
    hcc = np.clip(get("hcc"), 0, 100)
    tgrp_cum = get("tgrp")
    tirf_cum = get("tirf")
    tsnowp_cum = get("tsnowp")
    # Altitude réelle : fournie par l'appelant (SP2 H+0, mis en cache)
    if altitude is not None and np.any(np.isfinite(altitude)):
        h_alt = np.asarray(altitude, dtype=np.float64)
    else:
        h_alt = np.zeros(shape)

    fields = {}

    def put(name, arr):
        if arr is not None:
            fields[name] = arr

    # ── Cumuls → valeurs horaires ────────────────────────────────────────
    prev = previous or {}
    rain_total = np.where(np.isfinite(tirf_cum), np.maximum(tirf_cum, 0.0), np.nan)
    snow_total = np.where(np.isfinite(tsnowp_cum), np.maximum(tsnowp_cum, 0.0), np.nan)
    graupel_total = np.where(np.isfinite(tgrp_cum), np.maximum(tgrp_cum, 0.0), np.nan)
    if lead_hour == 0 and not np.any(np.isfinite(rain_total)):
        rain_total = np.zeros(shape)
    if lead_hour == 0 and not np.any(np.isfinite(snow_total)):
        snow_total = np.zeros(shape)
    if lead_hour == 0 and not np.any(np.isfinite(graupel_total)):
        graupel_total = np.zeros(shape)

    prev_rain = prev.get("rain_total")
    prev_snow = prev.get("snow_total")
    prev_graupel = prev.get("graupel_total")
    rain = np.where(np.isfinite(rain_total),
                    np.maximum(rain_total - (prev_rain if prev_rain is not None else 0.0), 0.0),
                    np.nan)
    snow = np.where(np.isfinite(snow_total),
                    np.maximum(snow_total - (prev_snow if prev_snow is not None else 0.0), 0.0),
                    np.nan)
    graupel = np.where(np.isfinite(graupel_total),
                       np.maximum(graupel_total - (prev_graupel if prev_graupel is not None else 0.0), 0.0),
                       np.nan)
    if prev_rain is None:
        rain[~np.isfinite(rain_total)] = np.nan

    # ── Réflectivité simulée (proxy Marshall-Palmer) ─────────────────────
    # Z = 200 · R^1,6 (R en mm/h, relation standard radar) → dBZ.
    # Pas de pluie ⇒ NaN (transparent sur la carte « Orages Simulés »,
    # et traité comme 0 dans les indices via nan_to_num).
    rain_hr = np.maximum(np.nan_to_num(rain, nan=0.0), 0.0)
    refl = np.where(rain_hr > 0.05,
                    10.0 * np.log10(200.0 * np.power(rain_hr, 1.6)),
                    np.nan)
    refl = np.clip(refl, 0, 80)

    # ── Vent ─────────────────────────────────────────────────────────────
    ws10 = np.hypot(np.nan_to_num(u10, nan=0.0), np.nan_to_num(v10, nan=0.0)) * 3.6
    ws10[~np.isfinite(u10) | ~np.isfinite(v10)] = np.nan
    gust = np.hypot(np.nan_to_num(efg_u, nan=0.0), np.nan_to_num(efg_v, nan=0.0)) * 3.6
    gust[~np.isfinite(efg_u) | ~np.isfinite(efg_v)] = np.nan
    wind_dir = (np.degrees(np.arctan2(-np.nan_to_num(u10, nan=0.0),
                                      -np.nan_to_num(v10, nan=0.0))) % 360.0)
    wind_dir[~np.isfinite(u10) | ~np.isfinite(v10)] = np.nan

    # Cisaillement vertical 10→100 m : proxy à partir des rafales
    # (le vent 100 m n'est plus publié en open data) :
    # shear ≈ (rafale − vent moyen) × 0,75 + 10, borné [5, 45] km/h.
    ws100 = np.full(shape, np.nan)
    shear = np.clip((np.nan_to_num(gust, nan=0.0)
                     - np.nan_to_num(ws10, nan=0.0)) * 0.75 + 10.0, 5.0, 45.0)
    shear[~np.isfinite(gust) | ~np.isfinite(ws10)] = np.nan

    # ── Point de rosée / ressenti / humidex ──────────────────────────────
    rel = np.clip(r2 / 100.0, 0.01, 1.0)
    gamma = np.log(rel) + 17.625 * t2m / (243.04 + t2m)
    dew = 243.04 * gamma / (17.625 - gamma)
    dew[~np.isfinite(t2m) | ~np.isfinite(r2)] = np.nan

    wind_chill = t2m.copy()
    chill_ok = np.isfinite(t2m) & np.isfinite(ws10) & (t2m <= 10) & (ws10 >= 4.8)
    wf = np.power(np.maximum(np.nan_to_num(ws10, nan=0.0), 0.0), 0.16)
    wind_chill[chill_ok] = (13.12 + 0.6215 * t2m[chill_ok]
                            - 11.37 * wf[chill_ok] + 0.3965 * t2m[chill_ok] * wf[chill_ok])

    td_k = np.clip(dew + 273.15, 173.15, 333.15)
    e = 6.11 * np.exp(5417.7530 * (1.0 / 273.16 - 1.0 / td_k))
    humidex = t2m + 0.5555 * (e - 10.0)

    # ── Nuages totaux (superposition) ────────────────────────────────────
    cloud = 100.0 * (1.0 - (1.0 - lcc / 100.0) * (1.0 - mcc / 100.0) * (1.0 - hcc / 100.0))
    cloud[~np.isfinite(lcc) | ~np.isfinite(mcc) | ~np.isfinite(hcc)] = np.nan

    # ── Pression MSL (réduction hypsométrique avec altitude réelle) ──────
    t_k = np.maximum(t2m + 273.15, 180.0)
    pressure = sp * np.exp(9.80665 * np.maximum(h_alt, -500.0)
                           / (287.05 * (t_k + 0.00325 * np.maximum(h_alt, 0.0))))
    pressure[~np.isfinite(sp) | ~np.isfinite(t2m)] = np.nan
    pressure = np.clip(pressure, 850, 1085)

    # ── Condition code (0-9, comme météociel) ────────────────────────────
    condition = np.zeros(shape, dtype=np.int16)
    condition[np.isfinite(cloud) & (cloud <= 20)] = 1
    condition[np.isfinite(cloud) & (cloud > 20) & (cloud <= 55)] = 2
    condition[np.isfinite(cloud) & (cloud > 55) & (cloud <= 85)] = 3
    condition[np.isfinite(cloud) & (cloud > 85)] = 4
    condition[np.isfinite(gust) & (gust >= 70)] = 9
    condition[np.isfinite(rain) & (rain >= 0.1)] = 5
    condition[np.isfinite(rain) & (rain >= 5.0)] = 6
    condition[np.isfinite(snow) & (snow >= 0.1)] = 7
    # Brouillard : humidité très élevée + nuages bas + vent faible
    fog = (r2 >= 96) & (lcc >= 90) & (ws10 < 10)
    condition[fog & np.isfinite(r2) & np.isfinite(lcc) & np.isfinite(ws10)] = 8

    # ── Diagnostics orageux ──────────────────────────────────────────────
        # ── Diagnostics orageux (Méthode officielle page commune) ────────────
    thunder = np.zeros(shape, dtype=np.int16)
    thunder[(cape >= 100) | (refl >= 30)] = 1
    thunder[(cape >= 500) | (refl >= 40)] = 2
    thunder[(cape >= 1200) | (refl >= 50)] = 3
    thunder[(cape >= 2200) & (refl >= 52)] = 4
    thunder[(refl >= 58) | ((cape >= 1800) & (gust >= 90))] = 4
    thunder[~np.isfinite(cape) & ~np.isfinite(refl)] = 0

    lightning = np.clip(
        np.nan_to_num(cape, nan=0.0) / 30.0
        + np.maximum(np.nan_to_num(refl, nan=0.0) - 25.0, 0) * 1.8,
        0, 100)

    hail = np.zeros(shape, dtype=np.int16)
    hail[(cape >= 500) & (refl >= 42)] = 1
    hail[(cape >= 1200) & (refl >= 50)] = 2
    hail[((cape >= 2200) & (refl >= 55)) | (graupel >= 2)] = 3

    conv_frac = np.clip(np.nan_to_num(cape, nan=0.0) / 1200.0, 0, 1) \
        * np.clip((np.nan_to_num(refl, nan=0.0) - 20.0) / 25.0, 0, 1)
    conv_precip = rain * conv_frac

    # Type d'orage — AMÉLIORÉ : cisaillement vertical 10→100 m inclus
    # 0 = pas d'orage organisé, 1 = cellules isolées, 2 = multicellulaire,
    # 3 = ligne/MCS, 4 = convection très intense / supercellulaire
    storm_type = np.zeros(shape, dtype=np.int16)
    storm_type[thunder == 1] = 1
    storm_type[thunder == 2] = 2
    strong_shear = np.nan_to_num(shear, nan=0.0) >= 40  # > 40 km/h de cisaillement
    storm_type[(thunder >= 3) & (refl >= 50) & strong_shear] = 3
    storm_type[(thunder >= 4) & (cape >= 2000)] = 4
    storm_type[(thunder >= 3) & (refl >= 50) & ~strong_shear] = 3

    # ── Diagnostics neige ────────────────────────────────────────────────
    snow_ratio = np.select(
        [t2m <= -10, t2m <= -5, t2m <= 0, t2m <= 1.5],
        [15.0, 12.0, 10.0, 6.0], default=2.0)
    snow_fresh = np.maximum(snow, 0.0) * snow_ratio / 10.0   # cm

    prev_fresh = prev.get("fresh_snow")
    if prev_fresh is None:
        snow_depth = snow_fresh.copy()
    else:
        snow_depth = np.nan_to_num(prev_fresh, nan=0.0) + np.nan_to_num(snow_fresh, nan=0.0)
        snow_depth[~np.isfinite(snow_fresh) & ~np.isfinite(prev_fresh)] = np.nan

    snow_phase = np.zeros(shape, dtype=np.int16)
    snow_phase[np.isfinite(rain) & (rain >= 0.1)] = 1
    snow_phase[(snow >= 0.03) & (t2m > 0.5)] = 2
    snow_phase[(snow >= 0.03) & (t2m <= 0.5)] = 3

    snow_stick = np.zeros(shape, dtype=np.int16)
    snow_stick[(snow_fresh >= 0.05) & (t2m <= 2.0)] = 1
    snow_stick[(snow_fresh >= 0.2) & (t2m <= 1.0)] = 2
    snow_stick[(snow_fresh >= 0.5) & (t2m <= 0.0)] = 3

    snow_risk = np.zeros(shape, dtype=np.int16)
    snow_risk[(snow >= 0.03) | ((rain >= 0.2) & (t2m <= 1.5))] = 1
    snow_risk[(snow_fresh >= 0.3) | ((rain >= 1.0) & (t2m <= 0.5))] = 2
    snow_risk[(snow_fresh >= 1.0) | ((rain >= 3.0) & (t2m <= 0.0))] = 3
    snow_risk[(snow_fresh >= 3.0) | ((rain >= 8.0) & (t2m <= -1.0))] = 4

    # ── LCL (formule de Lawrence) ────────────────────────────────────────
    lcl = np.clip(125.0 * (t2m - dew), 0, 5000)

    # ── IPO / IPG (mêmes formules que JS calculateIPO/calculateIPG) ──────
    # Interpolation piecewise CAPE (cterm)
    _cape = np.nan_to_num(cape, nan=0.0)
    _refl = np.nan_to_num(refl, nan=0.0)
    _grpl = np.nan_to_num(graupel, nan=0.0)
    _rain = np.nan_to_num(rain, nan=0.0)

    xp = np.array([0, 100, 300, 500, 750, 1000, 1500, 2000], dtype=np.float64)
    fp = np.array([0, 0.05, 0.25, 0.45, 0.65, 0.80, 0.95, 1.00], dtype=np.float64)
    cterm = np.interp(_cape, xp, fp)
    zterm = np.clip((_refl - 20.0) / 35.0, 0, 1)
    gterm = np.clip(_grpl / 2.0, 0, 1)
    rterm = np.clip((_rain - 0.2) / 14.8, 0, 1)
    ipo_base = 100.0 * (0.35 * cterm + 0.40 * zterm + 0.15 * gterm + 0.10 * rterm)
    # Bonus cohérence convective
    bonus = (
        np.where((_cape >= 500) & (_refl >= 35), 5.0, 0.0) +
        np.where((_cape >= 750) & (_refl >= 40), 5.0, 0.0) +
        np.where((_refl >= 40) & (_grpl >= 0.5), 5.0, 0.0) +
        np.where((_cape >= 1000) & (_refl >= 45) & (_grpl > 0), 5.0, 0.0)
    )
    ipo_arr = np.clip(ipo_base + bonus, 0, 100)
    # Verrou CAS1 (pas de convection simulée)
    no_conv = (_refl < 20) & (_rain < 0.2) & (_grpl == 0)
    caps = np.select(
        [_cape < 300, _cape < 500, _cape < 750, _cape < 1000, _cape < 1500],
        [5.0, 15.0, 25.0, 30.0, 35.0], default=40.0)
    ipo_arr = np.where(no_conv, np.minimum(ipo_arr, caps), ipo_arr)
    # Arrondi demi-entier IDENTIQUE au JS calculateIPO (Math.round = floor(x+0.5))
    # → cohérence absolue carte (tuiles/probes) ↔ fiche commune
    ipo_arr = np.floor(ipo_arr + 0.5)

    # IPG
    xp_g = np.array([0, 300, 500, 750, 1000, 1500, 2000, 2500], dtype=np.float64)
    fp_g = np.array([0, 0.05, 0.20, 0.40, 0.60, 0.80, 0.95, 1.00], dtype=np.float64)
    cgrele = np.interp(_cape, xp_g, fp_g)
    # zgrele v2 : adapté à la réflectivité Marshall-Palmer (35 dBZ ≈ 3 mm/h
    # → 55 dBZ ≈ 55 mm/h), au lieu du seuil 45-60 dBZ du champ direct.
    zgrele = np.clip((_refl - 35.0) / 20.0, 0, 1)
    ggrele = np.clip(_grpl / 2.0, 0, 1)
    ipg_arr = np.clip(100.0 * (0.45 * zgrele + 0.30 * cgrele + 0.25 * ggrele), 0, 100)
    # Verrous IPG v2 (adaptés réflectivité Marshall-Palmer)
    ipg_arr = np.where(_refl < 30, np.minimum(ipg_arr, 15.0), ipg_arr)
    ipg_arr = np.where((_refl < 35) & (_grpl == 0), np.minimum(ipg_arr, 10.0), ipg_arr)
    ipg_arr = np.where((_cape < 300) & (_grpl == 0), np.minimum(ipg_arr, 10.0), ipg_arr)
    ipg_arr = np.where(~((_refl >= 45) & (_cape >= 500)) & (_grpl < 0.5),
                       np.minimum(ipg_arr, 69.0), ipg_arr)
    # Arrondi demi-entier IDENTIQUE au JS calculateIPG (Math.round = floor(x+0.5))
    ipg_arr = np.floor(ipg_arr + 0.5)

    # IPT (Indice de Potentiel Tornadique 0-100) — formule identique au JS
    # calculateIPT. Recalibrage v2 aligné sur la recherche (Thompson et al. 2004,
    # STP SPC) : facteur LCL borné [0,1] (0 si LCL > 2000 m, 1 si LCL < 1000 m),
    # terme réflectivité borné [0,1], diviseur 2,5 (max théorique ≈ 69/100,
    # bande « Sévère » réservée aux environnements exceptionnels).
    _shear = np.nan_to_num(shear, nan=0.0)
    # shear_factor v2 : renormalisé pour le proxy rafales [5,45] km/h →
    # facteur [0,25 ; 2,25] (au lieu de /50 pensé pour le vent 100 m réel).
    shear_factor = np.clip(_shear / 20.0, 0.0, 2.5)
    lcl_factor = np.clip((2000.0 - lcl) / 1000.0, 0.0, 1.0)
    cape_factor = np.clip(_cape / 1500.0, 0.0, 2.0)
    refl_factor = np.clip(_refl / 65.0, 0.0, 1.0)
    raw_ipt = (100.0 * (0.35 * shear_factor + 0.30 * lcl_factor + 0.20 * cape_factor + 0.15 * refl_factor)) / 2.5
    has_storm = (_refl >= 32.0) & (_cape >= 350.0)
    # Arrondi demi-entier IDENTIQUE au JS calculateIPT (Math.round = floor(x+0.5))
    ipt_arr = np.where(has_storm, np.floor(np.clip(raw_ipt, 0.0, 100.0) + 0.5), 0.0)

    # ── Sortie ───────────────────────────────────────────────────────────
    put("temperature_c", t2m)
    put("wind_chill_c", wind_chill)
    put("dewpoint_c", dew)
    put("humidex", humidex)
    put("humidity_pct", r2)
    put("precipitation_mm", rain)
    put("precipitation_total_mm", rain_total)
    put("snowfall_mm", snow)
    put("snow_mm", snow)
    put("snow_fresh_cm", snow_fresh)
    put("snow_depth_cm", snow_depth)
    put("snow_water_equivalent_mm", snow_total)
    put("snowfall_total_mm", snow_total)
    put("graupel_mm", graupel)
    put("cloud_cover_pct", cloud)
    put("cloud_low_pct", lcc)
    put("cloud_mid_pct", mcc)
    put("cloud_high_pct", hcc)
    put("wind_speed_kmh", ws10)
    put("wind_direction_deg", wind_dir)
    put("wind_gust_kmh", gust)
    put("wind_100m_kmh", ws100)
    put("wind_shear_kmh", shear)
    put("pressure_hpa", pressure)
    put("pressure_surface_hpa", sp)
    put("surface_pressure_hpa", sp)
    put("cape_jkg", cape)
    put("reflectivity_dbz", refl)
    put("lcl_m", lcl)
    put("condition_code", condition)
    put("thunder_risk_code", thunder)
    put("lightning_score", lightning)
    put("hail_risk_code", hail)
    put("convective_precipitation_mm", conv_precip)
    put("storm_type_code", storm_type)
    put("snow_risk_code", snow_risk)
    put("snow_phase_code", snow_phase)
    put("snow_stick_risk_code", snow_stick)
    put("altitude_m", h_alt)
    put("ipo", ipo_arr)
    put("ipg", ipg_arr)
    put("instabilite", _cape)     # MUCAPE brut pour carte instabilite
    put("orages_simules", _refl)  # Réflectivité brute pour carte orages
    put("ipt", ipt_arr)           # Indice Potentiel Tornadique

    state = {
        "rain_total": rain_total,
        "snow_total": snow_total,
        "graupel_total": graupel_total,
        "fresh_snow": snow_depth,
    }
    return fields, state


# ── Extraction par commune ──────────────────────────────────────────────────
COMMUNES_FILE = os.path.join(BASE_DIR, "config", "communes-compact.json")

# Colonnes stockées par commune : nom, échelle (int16 = round(v/scale)),
# offset ajouté avant division (pour les valeurs négatives → int16 non signé)
COMMUNE_COLUMNS = [
    # (nom, scale, offset)  → valeur stockée = (v + offset) / scale
    ("temperature_c", 0.1, 600),        # -60..+60 °C → 0..1200
    ("wind_chill_c", 0.1, 600),
    ("dewpoint_c", 0.1, 600),
    ("humidex", 0.1, 600),
    ("humidity_pct", 1.0, 0),
    ("precipitation_mm", 0.01, 0),
    ("precipitation_total_mm", 0.1, 0),
    ("snowfall_mm", 0.01, 0),
    ("snow_fresh_cm", 0.1, 0),
    ("snow_depth_cm", 0.1, 0),
    ("snow_water_equivalent_mm", 0.1, 0),
    ("graupel_mm", 0.01, 0),
    ("cloud_cover_pct", 1.0, 0),
    ("cloud_low_pct", 1.0, 0),
    ("cloud_mid_pct", 1.0, 0),
    ("cloud_high_pct", 1.0, 0),
    ("wind_speed_kmh", 1.0, 0),
    ("wind_direction_deg", 1.0, 0),
    ("wind_gust_kmh", 1.0, 0),
    ("wind_gust_max_kmh", 1.0, 0),   # rafale max depuis le run (comme météociel)
    ("wind_100m_kmh", 1.0, 0),
    ("wind_shear_kmh", 1.0, 0),
    ("pressure_hpa", 0.1, 0),
    ("pressure_surface_hpa", 0.1, 0),
    ("cape_jkg", 1.0, 0),
    ("reflectivity_dbz", 0.1, 0),
    ("lcl_m", 5.0, 0),
    ("condition_code", 1.0, 0),
    ("thunder_risk_code", 1.0, 0),
    ("lightning_score", 1.0, 0),
    ("hail_risk_code", 1.0, 0),
    ("convective_precipitation_mm", 0.01, 0),
    ("storm_type_code", 1.0, 0),
    ("snow_risk_code", 1.0, 0),
    ("snow_phase_code", 1.0, 0),
    ("snow_stick_risk_code", 1.0, 0),
    ("altitude_m", 1.0, 500),           # -500..+5000 m
]

NAN_I16 = -32768


def load_communes():
    """Charge les communes : [[code, nom, postaux[], dept, pop, lat, lon], ...]"""
    import json
    with open(COMMUNES_FILE, encoding="utf-8") as f:
        return json.load(f)


def bilinear_sample(fields, communes):
    """Interpolation bilinéaire de chaque champ aux coordonnées exactes des
    communes. Retourne {nom_champ: array (n_communes,)}."""
    lats = np.array([c[5] for c in communes], dtype=np.float64)
    lons = np.array([c[6] for c in communes], dtype=np.float64)
    rows_f = (LAT0 - lats) / STEP
    cols_f = (lons - LON0) / STEP
    r0 = np.clip(np.floor(rows_f).astype(np.int64), 0, NJ - 2)
    c0 = np.clip(np.floor(cols_f).astype(np.int64), 0, NI - 2)
    fr = (rows_f - r0).astype(np.float64)
    fc = (cols_f - c0).astype(np.float64)
    r1, c1 = r0 + 1, c0 + 1

    out = {}
    for name, arr in fields.items():
        if arr is None:
            continue
        a = np.asarray(arr, dtype=np.float64)
        v00 = a[r0, c0]
        v01 = a[r0, c1]
        v10 = a[r1, c0]
        v11 = a[r1, c1]
        v = (v00 * (1 - fr) * (1 - fc) + v01 * (1 - fr) * fc
             + v10 * fr * (1 - fc) + v11 * fr * fc)
        out[name] = v
    return out


def quantize(values, scale, offset):
    q = np.round((values + offset) / scale)
    q = np.clip(q, -32767, 32767)
    q[~np.isfinite(values)] = NAN_I16
    return q.astype(np.int16)


# ── Grilles de valeurs pour la sonde (format HKV1, comme le front l'attend) ──
PROBE_W, PROBE_H = 440, 328  # grille réduite (facteur 5 vs 2200×1640)

def export_probe(field, out_path):
    """Exporte une grille 2D en format HKV1 gzip pour la sonde au survol.
    Structure : 'HKV1' + width u16 + height u16 + min f32 + max f32 + u16[…]
    (65535 = NaN)."""
    import gzip
    data = np.asarray(field, dtype=np.float64)
    ny, nx = data.shape
    fin = data[np.isfinite(data)]
    if fin.size == 0:
        min_val, max_val = 0.0, 1.0
    else:
        min_val = float(np.min(fin))
        max_val = float(np.max(fin))
    val_range = max_val - min_val if max_val > min_val else 1.0
    normalized = np.full(data.shape, 65535, dtype=np.uint16)
    ok = np.isfinite(data)
    normalized[ok] = np.clip(
        (data[ok] - min_val) / val_range * 65534.0, 0, 65534).astype(np.uint16)
    header = bytearray(b'HKV1')
    header.extend(np.uint16(nx).tobytes())
    header.extend(np.uint16(ny).tobytes())
    header.extend(np.float32(min_val).tobytes())
    header.extend(np.float32(max_val).tobytes())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with gzip.open(out_path, "wb") as f:
        f.write(bytes(header) + normalized.tobytes())


def save_probes(out_dir, lead, fields, step_files, regridded, tile_fields=None):
    """Écrit maps/values/{layer}/{lead}.hkv.gz pour chaque paramètre tuilé.
    step_files["probes"] = {layer: rel_path}."""
    if tile_fields is None:
        tile_fields = TILE_FIELDS
    probes = {}
    for tile_name, fname in tile_fields.items():
        data = regridded.get(tile_name)
        if data is None:
            continue
        # Sous-échantillonnage vers PROBE_W × PROBE_H (moyenne de blocs)
        sy = data.shape[0] // PROBE_H
        sx = data.shape[1] // PROBE_W
        if sy >= 1 and sx >= 1:
            small = np.nanmean(
                data[:PROBE_H * sy, :PROBE_W * sx].reshape(
                    PROBE_H, sy, PROBE_W, sx),
                axis=(1, 3))
        else:
            small = data
        rel = "maps/values/%s/%03d.hkv.gz" % (tile_name, lead)
        export_probe(small, os.path.join(out_dir, "..", rel.replace("/", os.sep)))
        probes[tile_name] = rel
    if probes:
        step_files["probes"] = probes


# ── Écriture des fichiers par département ───────────────────────────────────
def write_department_files(out_dir, run_str, leads, per_lead_values, communes):
    """per_lead_values : dict lead → dict champ → array (n_communes,).
    Écrit output/arome/communes/{dept}.bin.gz + index.json."""
    import json
    cdir = os.path.join(out_dir, "communes")
    os.makedirs(cdir, exist_ok=True)

    # Regroupe les communes par département (ordre du fichier)
    by_dept = {}
    for i, c in enumerate(communes):
        by_dept.setdefault(c[3], []).append(i)

    # Cumuls par commune et par échéance (pluie/neige totales déjà fournies)
    leads_sorted = sorted(leads)
    col_names = [c[0] for c in COMMUNE_COLUMNS]
    col_scales = [c[1] for c in COMMUNE_COLUMNS]
    col_offsets = [c[2] for c in COMMUNE_COLUMNS]

    for dept, idxs in by_dept.items():
        idxs = sorted(idxs)
        n = len(idxs)
        # Entête
        header = bytearray()
        header += b"MCV2"
        header += struct.pack("<H", n)                 # nb communes
        header += struct.pack("<H", len(leads_sorted))  # nb échéances
        header += struct.pack("<H", len(col_names))     # nb colonnes
        run_b = run_str.encode("ascii", "replace")[:40].ljust(40, b"\0")
        header += run_b
        # Communes : code(5) + nom variable + lat/lon + population
        for i in idxs:
            code = str(communes[i][0])[:5].encode("ascii", "replace").ljust(5, b"\0")
            nom = str(communes[i][1]).encode("utf-8")[:80]
            header += code
            header += struct.pack("<B", len(nom)) + nom
            header += struct.pack("<f", float(communes[i][5]))   # lat
            header += struct.pack("<f", float(communes[i][6]))   # lon
            header += struct.pack("<I", int(communes[i][4]))     # population
        # Colonnes : nom(32) + échelle + offset
        for cname, scale, offset in COMMUNE_COLUMNS:
            header += cname.encode("ascii", "replace")[:32].ljust(32, b"\0")
            header += struct.pack("<ff", scale, offset)
        # Échéances : heures
        for lh in leads_sorted:
            header += struct.pack("<H", lh)
        # Alignement des données sur 2 octets (exigé par Int16Array côté JS)
        if len(header) % 2 == 1:
            header += b"\0"

        # Données : construction vectorisée par échéance
        # mat[lead] = (n_communes, n_cols) en int16 → concaténation
        mats = []
        for lh in leads_sorted:
            pv = per_lead_values.get(lh)
            if pv is None:
                raise RuntimeError("Valeurs manquantes pour H+%d" % lh)
            n_cols = len(col_names)
            mat = np.empty((n, n_cols), dtype=np.int16)
            for j, (cname, scale, offset) in enumerate(COMMUNE_COLUMNS):
                arr = pv.get(cname)
                if arr is None:
                    mat[:, j] = NAN_I16
                    continue
                q = np.round((np.asarray(arr, dtype=np.float64)[idxs] + offset) / scale)
                q = np.clip(q, -32767, 32767)
                q[~np.isfinite(np.asarray(arr, dtype=np.float64)[idxs])] = NAN_I16
                mat[:, j] = q.astype(np.int16)
            mats.append(mat)
        data = np.concatenate(mats, axis=1).ravel() if mats else \
            np.zeros(0, dtype=np.int16)

        payload = bytes(header) + data.tobytes()
        gz = zlib.compress(payload, 9)
        with open(os.path.join(cdir, "%s.bin.gz" % dept), "wb") as f:
            f.write(gz)

    # index.json
    meta = {
        "format": "MCV2",
        "run_time": run_str,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat().replace("+00:00", "Z"),
        "columns": [c[0] for c in COMMUNE_COLUMNS],
        "leads": leads_sorted,
        "departments": {d: len(v) for d, v in by_dept.items()},
        "communes_total": len(communes),
    }
    with open(os.path.join(cdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    return cdir


# ── Rendu des tuiles ────────────────────────────────────────────────────────
def save_tile(name, arr, lat, lon, out_dir, lead, step_files, regridded):
    if arr is None:
        return
    if name not in regridded:
        try:
            regridded[name] = regrid(arr, lat, lon)
        except Exception as e:
            print("  [%s] regrid: %s" % (name, e))
            return
    data = regridded[name]
    # Bandes discrètes pour les indices qualitatifs (couleurs = légendes) ;
    # dégradé continu pour les champs physiques.
    rgba = apply_palette(data, PALETTES.get(name, PALETTES["temperature"]),
                         discrete=(name in DISCRETE_LAYERS))
    ddir = os.path.join(out_dir, name)
    os.makedirs(ddir, exist_ok=True)
    dst = os.path.join(ddir, "%03d.webp" % lead)
    Image.fromarray(rgba, "RGBA").save(dst, format="WEBP", quality=85, method=4)
    if "files" not in step_files:
        step_files["files"] = {}
    step_files["files"][name] = "maps/%s/%03d.webp" % (name, lead)


# Champs rendus en tuiles (compatibles palettes existantes)
TILE_FIELDS = {
    "temperature": "temperature_c",
    "temperature_ressentie": "wind_chill_c",
    "point_rosee": "dewpoint_c",
    "humidex": "humidex",
    "humidite": "humidity_pct",
    "pluie_1h": "precipitation_mm",
    "pluie_cumul": "precipitation_total_mm",
    "neige": "snowfall_mm",
    "neige_au_sol": "snow_depth_cm",
    "equivalent_eau_neige": "snow_water_equivalent_mm",
    "graupel": "graupel_mm",
    "nebulosite": "cloud_cover_pct",
    "nuages_bas": "cloud_low_pct",
    "nuages_moyens": "cloud_mid_pct",
    "nuages_eleves": "cloud_high_pct",
    "vent": "wind_speed_kmh",
    "rafales": "wind_gust_kmh",
    "rafales_cumul": "wind_gust_max_kmh",
    "pression": "pressure_hpa",
    "pression_surface": "pressure_surface_hpa",
    "mucape": "cape_jkg",
    "reflectivite": "reflectivity_dbz",
    "ipo": "ipo",
    "ipg": "ipg",
    "instabilite": "instabilite",
    "orages_simules": "orages_simules",
    "rafales_convectives": "wind_gust_kmh",
    "ipt": "ipt",
}

# Mode « Module Grêle » (--convective-only) : uniquement les couches du module
# convectif, rendues depuis le produit 0,025° (répertoires disjoints des cartes
# de base 1,3 km produites par l'automatisation habituelle).
CONVECTIVE_ONLY_LAYERS = ("ipo", "ipg", "ipt", "instabilite",
                          "orages_simules", "rafales_convectives")


def render_chunk(run_str, start, end, out_dir, steps, previous_state,
                 communes, per_lead_values, altitude_cache, synth=None,
                 run_dt=None, tile_fields=None, **kwargs):
    """Télécharge SP1+SP2 d'un chunk (7 échéances), puis décode/calcule/rend
    chaque échéance horaire (tuiles + échantillonnage communes + sondes)."""
    if tile_fields is None:
        tile_fields = TILE_FIELDS
    tmp = tempfile.mkdtemp(prefix="arome_grib_")
    try:
        paths = download_chunk(run_str, start, end, tmp)
        if len(paths) < 2:
            print("  Chunk %02dH-%02dH: paquets insuffisants (%d)"
                  % (start, end, len(paths)))
            return False

        lats = LAT0 - np.arange(NJ) * STEP
        lons = LON0 + np.arange(NI) * STEP

        for lead in range(start, end + 1):
            step_files = {}
            raw = {}
            for p in paths:
                raw.update(read_grib(p, run_str, lead))

            if lead == 0:
                if "h" in raw:
                    altitude_cache["h"] = _clean(raw["h"])
                    print("  Altitude chargée (min %.0f m, max %.0f m)"
                          % (np.nanmin(altitude_cache["h"]),
                             np.nanmax(altitude_cache["h"])))
                else:
                    print("  WARNING: altitude absente H+0")
            altitude = altitude_cache.get("h", np.zeros((NJ, NI)))

            if "t2m" not in raw and "cape" not in raw:
                print("  H+%02d: aucun champ décodé" % lead)
                continue

            fields, state = compute_fields(raw, altitude, previous_state, lead)
            if not fields:
                print("  H+%02d: aucun champ calculé" % lead)
                continue
            # CRITIQUE : réinjecte l'état des cumuls (rain_total, snow_total,
            # graupel_total, fresh_snow) pour que l'échéance suivante calcule
            # les valeurs HORAIRES par différence (cumul(H+n) − cumul(H+n−1)).
            previous_state.update(state)

            # Synthèses 24h J0/J+1 (max glissant sur la grille native)
            if synth is not None and run_dt is not None:
                update_synth(synth, fields, run_dt, lead)

            # ── Tuiles ─────────────────────────────────────────────────
            regridded = {}
            for tile_name, fname in tile_fields.items():
                arr = fields.get(fname)
                if arr is not None:
                    save_tile(tile_name, arr, lats, lons, out_dir, lead,
                              step_files, regridded)

            # Rafale max cumulée depuis le run (paramètre « rafale max échéance »).
            # NB : à H+0 les rafales sont NaN (pas de max sur un intervalle vide) ;
            # on initialise à 0 pour que le cumul ne soit pas pollué par NaN.
            if "rafales_cumul" in tile_fields:
                prev_max = previous_state.get("gust_max")
                cur_gust = fields["wind_gust_kmh"]
                if prev_max is None:
                    gust_max = np.where(np.isfinite(cur_gust), cur_gust, 0.0)
                else:
                    gust_max = np.maximum(np.nan_to_num(prev_max, nan=0.0),
                                          np.nan_to_num(cur_gust, nan=0.0))
                    gust_max[~np.isfinite(prev_max) & ~np.isfinite(cur_gust)] = np.nan
                previous_state["gust_max"] = gust_max
                fields["wind_gust_max_kmh"] = gust_max
                save_tile("rafales_cumul", gust_max, lats, lons, out_dir, lead,
                          step_files, regridded)

            # ── Échantillonnage par commune ────────────────────────────
            sampled = bilinear_sample(fields, communes)
            per_lead_values[lead] = sampled

            # ── Grilles de valeurs pour la sonde au survol ─────────────
            save_probes(out_dir, lead, fields, step_files, regridded,
                        tile_fields=tile_fields)

            # Rendu AROME-PE (Probabilités — désactivé)
            if "steps_pe" in kwargs:
                try:
                    from arome_pe_engine import render_pe_step
                    out_pe_dir = os.path.join(OUT_BASE, "arome_pe", "maps")
                    step_files_pe = {}
                    # Injection des champs 24h pour le moteur de probabilités PE
                    fields["rain_cumul_24h"] = fields.get("precipitation_total_mm", np.zeros_like(lats))
                    fields["gust_max_24h"] = fields.get("wind_gust_max_kmh", np.zeros_like(lats))
                    fields["tmax_24h"] = fields.get("temperature_max_24h", fields.get("temperature_c", np.zeros_like(lats)))
                    fields["tmin_24h"] = fields.get("temperature_min_24h", fields.get("temperature_c", np.zeros_like(lats)))
                    fields["snow_cumul_24h"] = fields.get("snow_depth_cm", np.zeros_like(lats))

                    # render_pe_step(fields, lead, out_pe_dir, step_files_pe, lats, lons)  # PE desactive
                    if step_files_pe:
                        vt = datetime.datetime.fromisoformat(run_str.replace("Z", "+00:00")) \
                            + datetime.timedelta(hours=lead)
                        kwargs["steps_pe"].append({
                            "lead_hour": lead,
                            "valid_time": vt.isoformat(),
                            "files": step_files_pe.get("files", {}),
                            "probes": step_files_pe.get("probes", {})
                        })
                except Exception as e:
                    print("  WARNING: AROME-PE non rendu H+%02d (%s)" % (lead, e))

            if step_files:
                vt = datetime.datetime.fromisoformat(run_str.replace("Z", "+00:00")) \
                    + datetime.timedelta(hours=lead)
                steps.append({"lead_hour": lead, "valid_time": vt.isoformat(),
                              "files": step_files.get("files", {}),
                              "probes": step_files.get("probes", {})})
                print("  H+%02d: %d champs, %d tuiles, %d probes, %d communes échantillonnées"
                      % (lead, len(fields), len(step_files.get("files", {})),
                         len(step_files.get("probes", {})), len(communes)))
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run(max_hours=51, convective_only=False):
    """Génère les tuiles AROME + prévisions par commune + synthèses.

    convective_only=True : « Module Grêle » — uniquement les 6 couches
    convectives (IPO, IPG, IPT, Instabilité, Orages simulés, Rafales) +
    synthèses 24h J0/J1 + fichiers communaux. SANS manifeste ni cartes de
    base (produites par l'automatisation 1,3 km habituelle)."""
    run_str = latest_run()
    leads = available_leads(run_str)
    print("Run AROME: %s | échéances disponibles: %s" % (run_str, len(leads)))
    out_dir = os.path.join(OUT_BASE, "arome", "maps")
    os.makedirs(out_dir, exist_ok=True)

    communes = load_communes()
    print("Communes chargées: %d" % len(communes))

    tile_fields = TILE_FIELDS
    if convective_only:
        tile_fields = {k: v for k, v in TILE_FIELDS.items()
                       if k in CONVECTIVE_ONLY_LAYERS}
        print("Mode MODULE GRÊLE : %d couches convectives (source 0,025°)"
              % len(tile_fields))

    steps = []
    steps_pe = []
    previous_state = {}
    per_lead_values = {}
    altitude_cache = {}
    run_dt = datetime.datetime.fromisoformat(run_str.replace("Z", "+00:00"))
    synth = {"j0": {}, "j1": {}}
    for s, e in CHUNKS:
        if s > max_hours:
            break
        render_chunk(run_str, s, e, out_dir, steps, previous_state,
                     communes, per_lead_values, altitude_cache,
                     steps_pe=steps_pe, synth=synth, run_dt=run_dt,
                     tile_fields=tile_fields)

    # Synthèses 24h J0 / J+1 (max de la journée locale)
    save_syntheses(synth, out_dir)

    # Fichiers par département + index
    write_department_files(out_dir, run_str,
                           [s["lead_hour"] for s in steps],
                           per_lead_values, communes)

    if convective_only:
        # Le manifeste index.json appartient à l'automatisation habituelle
        # (cartes de base 1,3 km) — on n'y touche pas en mode module.
        print("OK Module Grêle : %d échéances, %d communes (sans manifeste)"
              % (len(steps), len(communes)))
        return

    # Fond de carte (pays voisins inclus) + masque France (bornes correctes)
    try:
        from generate_fond import generate_all
        generate_all()
    except Exception as e:
        print("WARNING: fond de carte non généré (%s)" % e)

    from fetch_and_render_all import write_manifest
    meta = {"name": "AROME HD (2,5 km)", "provider": "Meteo-France",
            "resolution": "2,5 km (0.025°)", "run_time": run_str}
    write_manifest(out_dir, steps, meta)

    # Manifest AROME-PE
    try:
        from arome_pe_engine import write_pe_manifest
        out_pe_dir = os.path.join(OUT_BASE, "arome_pe", "maps")
        write_pe_manifest(out_pe_dir, steps_pe, run_str)
    except Exception as e:
        print("WARNING: AROME-PE Manifest non écrit (%s)" % e)
    print("OK AROME open data : %d échéances, %d communes"
          % (len(steps), len(communes)))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Pipeline AROME 0,025° (Module Grêle)")
    ap.add_argument("--max-hours", type=int, default=51,
                    help="Échéance max (0-51)")
    ap.add_argument("--convective-only", action="store_true",
                    help="Module Grêle : seulement les 6 couches convectives "
                         "+ communes + synthèses (sans manifeste)")
    args = ap.parse_args()
    run(max_hours=args.max_hours, convective_only=args.convective_only)
