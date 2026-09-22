#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arome_om.py — Pipeline de téléchargement et rendu AROME Outre-Mer (Antilles & Réunion).
========================================================================================
Télécharge les GRIB2 officiels haute résolution (0.025° ~ 2.5 km) sur le S3 PNT Météo-France
et génère les tuiles WebP, fonds et manifestes pour :
  - Arc Antillais & Caraïbes  -> output/arome_antilles/maps/
  - La Réunion & Mayotte      -> output/arome_reunion/maps/
"""

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.request

import eccodes
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "pipeline"))
from domains import DOMAINS, Domain  # noqa: E402
from palettes_data import PALETTES   # noqa: E402
from fetch_and_render_all import apply_palette  # noqa: E402

S3_BASE = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{run}/arome-om/{sub}/0025/{pkg}/arome-om-{sub}__0025__{pkg}__{lead:03d}H__{run}.grib2"

CONFIGS = {
    "antilles": {
        "sub": "ANTIL",
        "domain": "antilles",
        "out_dir": os.path.join(BASE_DIR, "output", "arome_antilles", "maps"),
        "model_name": "AROME Outre-Mer Arc Antillais",
        "badge": "2,5 km",
        "dataset_api": "https://www.data.gouv.fr/api/1/datasets/65bd162b9dc0d31edfabc2b9/"
    },
    "reunion": {
        "sub": "INDIEN",
        "domain": "reunion",
        "out_dir": os.path.join(BASE_DIR, "output", "arome_reunion", "maps"),
        "model_name": "AROME Outre-Mer La Réunion & Mayotte",
        "badge": "2,5 km",
        "dataset_api": "https://www.data.gouv.fr/api/1/datasets/65bd1560c73941a5e0ec1891/"
    }
}

LAYERS = [
    "temperature", "vent", "rafales", "pluie_1h", "pluie_cumul",
    "humidite", "point_rosee", "pression", "nuages", "mucape"
]


def find_latest_run(sub):
    """Détecte le dernier run disponible sur le S3."""
    now = datetime.datetime.now(datetime.timezone.utc)
    for delta_h in range(0, 36, 6):
        cand = (now - datetime.timedelta(hours=delta_h))
        run_h = (cand.hour // 6) * 6
        run_str = f"{cand.year:04d}-{cand.month:02d}-{cand.day:02d}T{run_h:02d}:00:00Z"
        url = S3_BASE.format(run=run_str, sub=sub, pkg="SP1", lead=0)
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "antigravity")
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    return run_str
        except Exception:
            continue
    return None


def download_lead_packages(run_str, sub, lead, tmpdir):
    """Télécharge SP1 et SP2 pour une échéance donnée."""
    files = {}
    for pkg in ("SP1", "SP2"):
        url = S3_BASE.format(run=run_str, sub=sub, pkg=pkg, lead=lead)
        dest = os.path.join(tmpdir, f"{pkg}_{lead:03d}.grib2")
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "antigravity")
            with urllib.request.urlopen(req, timeout=45) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            files[pkg] = dest
        except Exception as e:
            pass
    return files


def extract_fields(files):
    """Lit les messages GRIB2 et extrait les grilles 2D."""
    raw = {}
    src_lats = None
    src_lons = None

    for pkg, path in files.items():
        with open(path, "rb") as f:
            while True:
                gid = eccodes.codes_grib_new_from_file(f)
                if gid is None:
                    break
                sname = eccodes.codes_get(gid, "shortName")
                try:
                    lev = eccodes.codes_get(gid, "level")
                    lev_type = eccodes.codes_get(gid, "typeOfLevel")
                except Exception:
                    lev, lev_type = 0, "surface"

                if src_lats is None:
                    ni = eccodes.codes_get(gid, "Ni")
                    nj = eccodes.codes_get(gid, "Nj")
                    lat0 = eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
                    lon0 = eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
                    lat1 = eccodes.codes_get(gid, "latitudeOfLastGridPointInDegrees")
                    lon1 = eccodes.codes_get(gid, "longitudeOfLastGridPointInDegrees")
                    if lon0 > 180.0: lon0 -= 360.0
                    if lon1 > 180.0: lon1 -= 360.0
                    src_lats = np.linspace(lat0, lat1, nj, dtype=np.float64)
                    src_lons = np.linspace(lon0, lon1, ni, dtype=np.float64)

                vals = eccodes.codes_get_values(gid)
                arr = vals.reshape((len(src_lats), len(src_lons))).astype(np.float32)

                # Clé unique
                key = f"{sname}_{lev_type}_{lev}"
                raw[key] = arr
                raw[sname] = arr
                eccodes.codes_release(gid)

    return raw, src_lats, src_lons


def process_lead(raw, prev_tp, lead):
    """Calcule les champs finaux prêts pour application de palette."""
    out = {}

    # Température à 2 m (Kelvin -> Celsius)
    if "2t" in raw:
        out["temperature"] = raw["2t"] - 273.15
    elif "t" in raw:
        out["temperature"] = raw["t"] - 273.15

    # Point de rosée (Kelvin -> Celsius)
    if "2d" in raw:
        out["point_rosee"] = raw["2d"] - 273.15
    elif "d" in raw:
        out["point_rosee"] = raw["d"] - 273.15

    # Humidité relative
    if "2r" in raw:
        out["humidite"] = np.clip(raw["2r"], 0.0, 100.0)
    elif "r" in raw:
        out["humidite"] = np.clip(raw["r"], 0.0, 100.0)

    # Vent et rafales (m/s -> km/h)
    u = raw.get("10u", raw.get("u"))
    v = raw.get("10v", raw.get("v"))
    if u is not None and v is not None:
        out["vent"] = np.hypot(u, v) * 3.6
    if "10fg" in raw:
        out["rafales"] = raw["10fg"] * 3.6
    elif "gust" in raw:
        out["rafales"] = raw["gust"] * 3.6
    elif "vent" in out:
        out["rafales"] = out["vent"] * 1.35

    # Précipitations
    tp = raw.get("tp")
    if tp is not None:
        out["pluie_cumul"] = np.clip(tp, 0.0, None)
        if prev_tp is not None:
            out["pluie_1h"] = np.clip(tp - prev_tp, 0.0, None)
        else:
            out["pluie_1h"] = np.zeros_like(tp)

    # Pression niveau mer (Pa -> hPa)
    for p_key in ("prmsl", "mslet", "pres"):
        if p_key in raw:
            out["pression"] = raw[p_key] / 100.0
            break

    # Nuages (%)
    if "tcc" in raw:
        tcc = raw["tcc"]
        if tcc.max() <= 1.05:
            tcc = tcc * 100.0
        out["nuages"] = np.clip(tcc, 0.0, 100.0)

    # MUCAPE (J/kg)
    if "cape" in raw:
        out["mucape"] = np.clip(raw["cape"], 0.0, None)

    return out, tp


def render_domain(dom_key, max_hours=48, target_run=None):
    cfg = CONFIGS[dom_key]
    dom = Domain(cfg["domain"])
    out_dir = cfg["out_dir"]
    os.makedirs(out_dir, exist_ok=True)

    run_str = target_run or find_latest_run(cfg["sub"])
    if not run_str:
        print(f"[{dom_key}] Aucun run valide trouvé.")
        return False

    print(f"[{dom_key}] Lancement AROME-OM {cfg['sub']} — Run {run_str} (jusqu'à H+{max_hours:02d})")

    # Structure répertoires couches
    for lay in LAYERS:
        os.makedirs(os.path.join(out_dir, lay), exist_ok=True)

    prev_tp = None
    rendered_steps = []
    run_dt = datetime.datetime.fromisoformat(run_str.replace("Z", "+00:00"))

    with tempfile.TemporaryDirectory() as tmpdir:
        for lead in range(0, max_hours + 1):
            files = download_lead_packages(run_str, cfg["sub"], lead, tmpdir)
            if not files:
                print(f"[{dom_key}] H+{lead:03d} non disponible (arrêt des échéances).")
                break

            raw, src_lats, src_lons = extract_fields(files)
            if not raw or src_lats is None:
                continue

            fields, cur_tp = process_lead(raw, prev_tp, lead)
            prev_tp = cur_tp

            # Regrid et rendu de chaque couche
            for lay, arr in fields.items():
                if lay not in PALETTES:
                    continue
                regridded = dom.regrid(arr, src_lats, src_lons)
                pal = PALETTES.get(lay, PALETTES.get("temperature"))
                rgba = apply_palette(regridded, pal)
                img = Image.fromarray(rgba)
                tile_path = os.path.join(out_dir, lay, f"{lead:03d}.webp")
                img.save(tile_path, "WEBP", quality=85)

            # Date échéance
            valid_dt = run_dt + datetime.timedelta(hours=lead)
            rendered_steps.append({
                "lead_hour": lead,
                "step": lead,
                "valid_time": valid_dt.isoformat(),
                "date": valid_dt.strftime("%Y-%m-%d %H:%M UTC"),
                "files": {lay: f"maps/{lay}/{lead:03d}.webp" for lay in fields if lay in PALETTES}
            })

            print(f"[{dom_key}] H+{lead:02d} rendu avec succès ({len(fields)} couches).", flush=True)

            # Nettoyage fichiers temporaires
            for p in files.values():
                if os.path.exists(p): os.remove(p)

    # Manifeste index.json
    manifest = {
        "model": dom_key,
        "model_name": cfg["model_name"],
        "badge": cfg["badge"],
        "provider": "Météo-France",
        "resolution": "0.025° (~2.5 km)",
        "run": run_str,
        "run_time": run_dt.isoformat(),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bounds": {"south": dom.bounds[0], "west": dom.bounds[1], "north": dom.bounds[2], "east": dom.bounds[3]},
        "overlay": "maps/frontieres.svg",
        "fond": "maps/fond.webp",
        "mask": "maps/mask_france.png",
        "places": "maps/communes.json",
        "layers": {lay: {"label": lay.capitalize()} for lay in LAYERS},
        "steps": rendered_steps
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[{dom_key}] Terminé avec succès : {len(rendered_steps)} pas de temps écrits dans {out_dir}.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="all", choices=["antilles", "reunion", "all"])
    parser.add_argument("--max-hours", type=int, default=48)
    parser.add_argument("--run", type=str, default=None)
    args = parser.parse_args()

    doms = ["antilles", "reunion"] if args.domain == "all" else [args.domain]
    for d in doms:
        render_domain(d, max_hours=args.max_hours, target_run=args.run)


if __name__ == "__main__":
    main()

