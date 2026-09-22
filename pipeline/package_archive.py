#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_archive.py — Générateur d'archives MÉTÉO ÉLITE « PHOTOS D'ANTENNE HD » WebP
===================================================================================
- Périmètre : France Entière + Hauts-de-France uniquement.
- Échéances : TOUTES les échéances disponibles (H+00 à H+51 heure par heure).
- Organisation : Sous-dossiers propres et classés par paramètre météo pour chaque zone.
- Cartouche d'antenne : Ultra-compact et discret pour ne pas masquer les terres.
- Nommage : Jour de la semaine, date, heure locale et échéance.
"""

import os
import shutil
import zipfile
import math
import json
from datetime import datetime, timezone, timedelta
import zoneinfo
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

CATEGORIES_FRANCE = {
    "01_ORAGES_ET_GRELE": {
        "ipo": ("01_Potentiel_Orageux_IPO", "Indice Potentiel Orageux (IPO)", "/100", (0, 100)),
        "ipg": ("02_Potentiel_Grele_IPG", "Indice Potentiel Grêle (IPG)", "/100", (0, 100)),
        "orages_simules": ("03_Orages_Simules_Radar_dBZ", "Réflectivité Radar Simulée", "dBZ", (5, 65)),
        "instabilite": ("04_Instabilite_MUCAPE_Jkg", "Instabilité MUCAPE", "J/kg", (0, 3500)),
        "rafales_convectives": ("05_Rafales_Convectives_kmh", "Rafales sous Orages", "km/h", (0, 150)),
        "ipt": ("06_Potentiel_Tornadique_IPT", "Indice Potentiel Tornadique", "/100", (0, 100))
    },
    "02_TEMPERATURE": {
        "temperature": ("01_Temperature_2m_C", "Température à 2 mètres", "°C", (-15, 45))
    },
    "03_PRECIPITATIONS_ET_NEIGE": {
        "pluie_1h": ("01_Pluie_Horaire_1h_mm", "Précipitations en 1h", "mm/h", (0, 50)),
        "pluie_cumul": ("02_Pluie_Cumulee_Totale_mm", "Précipitations Cumulées", "mm", (0, 150)),
        "neige": ("03_Chutes_de_Neige_1h_mm", "Chutes de Neige en 1h", "cm/h", (0, 20)),
        "neige_au_sol": ("04_Epaisseur_Neige_au_Sol_cm", "Neige au Sol", "cm", (0, 100)),
        "graupel": ("05_Gresil_Graupel_mm", "Grésil / Graupel", "mm", (0, 25))
    },
    "04_VENTS_ET_RAFALES": {
        "vent": ("01_Vent_Moyen_10m_kmh", "Vent Moyen à 10m", "km/h", (0, 120)),
        "rafales": ("02_Rafales_Instantanees_10m_kmh", "Rafales de Vent à 10m", "km/h", (0, 160)),
        "rafales_cumul": ("03_Rafales_Max_Cumulees_kmh", "Rafales Maximales", "km/h", (0, 160))
    }
}

CATEGORIES_HDF = {
    "01_Temperature_2m": ("temperature", "Température à 2 mètres", "°C", (-15, 45)),
    "02_Pluie_Horaire_1h": ("pluie_1h", "Précipitations en 1h", "mm/h", (0, 50)),
    "03_Pluie_Cumulee_Totale": ("pluie_cumul", "Précipitations Cumulées", "mm", (0, 150)),
    "04_Vent_Moyen_10m": ("vent", "Vent Moyen à 10m", "km/h", (0, 120)),
    "05_Rafales_Max_10m": ("rafales", "Rafales de Vent à 10m", "km/h", (0, 160)),
    "06_Potentiel_Grele_IPG": ("ipg", "Indice Potentiel Grêle (IPG)", "/100", (0, 100))
}

HDF_CROP = (693, 112, 1523, 730)
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

def get_system_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()

def get_local_datetime_info(run_dt_utc, lead_hours):
    try:
        tz_paris = zoneinfo.ZoneInfo("Europe/Paris")
    except Exception:
        tz_paris = timezone(timedelta(hours=2))
    
    valid_dt = (run_dt_utc + timedelta(hours=lead_hours)).astimezone(tz_paris)
    jour_nom = JOURS_FR[valid_dt.weekday()]
    jour_court = jour_nom[:3]
    date_str = valid_dt.strftime("%d/%m")
    heure_str = f"{valid_dt.hour:02d}h{valid_dt.minute:02d}"
    
    label_antenne = f"{jour_court}. {date_str} {heure_str}"
    label_fichier = f"{jour_nom}_{valid_dt.strftime('%d-%m')}_{heure_str}"
    return label_antenne, label_fichier, jour_nom

README_INDEX_TEXT = """===============================================================================
ARCHIVES METEO ÉLITE « PHOTOS D'ANTENNE HD » WebP — AROME METEO-FRANCE
===============================================================================
Date et Run : {date_str} ({run_str})
Échéances : TOUTES les échéances horaires (H+00 à H+51 heure par heure)
Zones : France Entière + Hauts-de-France
Organisation : Classé par sous-dossiers thématiques pour chaque paramètre
Format : WebP haute qualité ultra-léger

STRUCTURE DES DOSSIERS :
- 00_FRANCE_ENTIERE/
    * 01_ORAGES_ET_GRELE/ (IPO, IPG, Radar dBZ, CAPE, Rafales, IPT)
    * 02_TEMPERATURE/ (T2m)
    * 03_PRECIPITATIONS_ET_NEIGE/ (Pluie 1h, Cumuls, Neige 1h, Neige sol, Gresil)
    * 04_VENTS_ET_RAFALES/ (Vent 10m, Rafales, Rafales max)

- 01_HAUTS_DE_FRANCE/
    * 01_Temperature_2m/
    * 02_Pluie_Horaire_1h/
    * 03_Pluie_Cumulee_Totale/
    * 04_Vent_Moyen_10m/
    * 05_Rafales_Max_10m/
    * 06_Potentiel_Grele_IPG/

- 02_SYNTHESES_24H/
    * Photos de synthese 24h maximales
===============================================================================
"""

def draw_compact_broadcast_overlay(img, param_title, unit_str, min_val, max_val, lead_hour, region_title, run_str, date_antenne_str):
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    
    is_regional = (w <= 850)
    
    # Tailles de polices compactes adaptées
    f_title = get_system_font(13 if is_regional else 16, bold=True)
    f_sub = get_system_font(10 if is_regional else 12, bold=True)
    f_lead = get_system_font(11 if is_regional else 13, bold=True)
    f_logo = get_system_font(11 if is_regional else 13, bold=True)
    f_leg = get_system_font(10 if is_regional else 12, bold=True)

    # 1. Cartouche d'antenne discret (En haut à gauche)
    bw = 285 if is_regional else 360
    bh = 68 if is_regional else 82
    draw.rounded_rectangle((12, 12, 12 + bw, 12 + bh), radius=8, fill=(7, 11, 20, 235), outline=(0, 210, 255, 180), width=1)
    
    full_title = f"{param_title} ({unit_str})" if unit_str else param_title
    draw.text((20, 18 if is_regional else 20), full_title, font=f_title, fill=(255, 255, 255, 255))
    draw.text((20, 36 if is_regional else 42), f"AROME HD (1,3 km) • {run_str}", font=f_sub, fill=(0, 210, 255, 255))
    draw.text((20, 50 if is_regional else 58), f"Échéance H+{lead_hour:02d} • {date_antenne_str} • {region_title}", font=f_lead, fill=(255, 255, 255, 255))

    # 2. Logo Météo-Climat Pro compact (En haut à droite)
    lw = 135 if is_regional else 160
    lh = 32 if is_regional else 38
    lx0 = w - lw - 12
    ly0 = 12
    draw.rounded_rectangle((lx0, ly0, lx0 + lw, ly0 + lh), radius=6, fill=(7, 11, 20, 235), outline=(255, 215, 0, 160), width=1)
    draw.text((lx0 + (10 if is_regional else 12), ly0 + (9 if is_regional else 11)), "MÉTÉO-CLIMAT", font=f_logo, fill=(255, 255, 255, 255))
    draw.text((lx0 + (100 if is_regional else 122), ly0 + (9 if is_regional else 11)), "PRO", font=f_logo, fill=(0, 210, 255, 255))

    # 3. Légende colorimétrique discrète en bas au centre
    leg_w = min(420 if is_regional else 520, int(w * 0.65))
    leg_h = 46 if is_regional else 54
    leg_x0 = (w - leg_w) // 2
    leg_y0 = h - leg_h - 12
    draw.rounded_rectangle((leg_x0, leg_y0, leg_x0 + leg_w, leg_y0 + leg_h), radius=8, fill=(7, 11, 20, 240), outline=(0, 210, 255, 160), width=1)
    
    draw.text((leg_x0 + leg_w // 2, leg_y0 + 4), full_title, font=f_leg, fill=(255, 255, 255, 255), anchor="mt")
    
    bar_w = leg_w - 36
    bar_x0 = leg_x0 + 18
    bar_y0 = leg_y0 + 18 if is_regional else leg_y0 + 22
    bar_h = 8 if is_regional else 10
    for x in range(bar_w):
        val_norm = x / float(bar_w)
        r = int(min(255, max(0, val_norm * 2 * 255)))
        b = int(min(255, max(0, (1 - val_norm * 1.5) * 255)))
        g = int(min(255, max(0, math.sin(val_norm * math.pi) * 255)))
        draw.line((bar_x0 + x, bar_y0, bar_x0 + x, bar_y0 + bar_h), fill=(r, g, b, 255))
    
    draw.text((bar_x0, bar_y0 + bar_h + 2), f"{min_val}", font=f_leg, fill=(203, 213, 225, 255), anchor="lt")
    draw.text((bar_x0 + bar_w // 2, bar_y0 + bar_h + 2), f"{(min_val + max_val) // 2}", font=f_leg, fill=(203, 213, 225, 255), anchor="mt")
    draw.text((bar_x0 + bar_w, bar_y0 + bar_h + 2), f"{max_val}", font=f_leg, fill=(203, 213, 225, 255), anchor="rt")

def process_single_photo(task):
    src_f, dst_f, fond_img, front_img, crop_box, target_size, param_title, unit_str, min_val, max_val, lead_hour, region_title, run_str, date_antenne_str = task
    try:
        with Image.open(src_f) as weather_layer:
            weather_rgba = weather_layer.convert("RGBA")
            comp = Image.alpha_composite(fond_img, weather_rgba)
            comp = Image.alpha_composite(comp, front_img).convert("RGB")
            if crop_box:
                comp = comp.crop(crop_box)
            comp_small = comp.resize(target_size, Image.Resampling.LANCZOS)
            
            draw_compact_broadcast_overlay(comp_small, param_title, unit_str, min_val, max_val, lead_hour, region_title, run_str, date_antenne_str)
            
            with open(dst_f, "wb") as f_out:
                comp_small.save(f_out, "WEBP", quality=75, method=6)
            return True
    except Exception:
        return False

def package_daily_archive(maps_dir="output/arome/maps", out_zip_name=None, only_major_runs=True):
    if not os.path.exists(maps_dir):
        print(f"Erreur : Repertoire {maps_dir} introuvable.")
        return None, 0, 0

    manifest_path = os.path.join(maps_dir, "index.json")
    run_dt = datetime.now(timezone.utc)
    run_hour_str = "12Z"
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
                r_time = mdata.get("run_time")
                if r_time:
                    run_dt = datetime.fromisoformat(r_time.replace("Z", "+00:00"))
                    run_hour_str = f"{run_dt.hour:02d}Z"
        except Exception:
            pass

    if only_major_runs and run_hour_str not in ["00Z", "12Z"]:
        print(f"ℹ️ Le run actuel ({run_hour_str}) n'est ni 00Z ni 12Z. Archivage ignore.")
        if not out_zip_name:
            return None, 0, 0

    try:
        tz_paris = zoneinfo.ZoneInfo("Europe/Paris")
    except Exception:
        tz_paris = timezone(timedelta(hours=2))
    
    local_run_dt = run_dt.astimezone(tz_paris)
    jour_run_nom = JOURS_FR[local_run_dt.weekday()]
    date_run_str = local_run_dt.strftime("%d-%m-%Y")
    run_label_clean = f"run_{run_hour_str.lower()}"

    if not out_zip_name:
        out_zip_name = f"arome_{jour_run_nom}_{date_run_str}_{run_label_clean}.zip"

    temp_root = f"temp_archive_hdf_{local_run_dt.strftime('%Y%m%d_%H%M')}"
    if os.path.exists(temp_root):
        try:
            shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            pass
    os.makedirs(temp_root, exist_ok=True)

    print(f"📦 Preparation de l'archive COMPLÈTE ({jour_run_nom} {date_run_str} {run_hour_str}) pour France + Hauts-de-France...")

    fond_path = os.path.join(maps_dir, "fond.webp")
    if not os.path.exists(fond_path):
        fond_path = os.path.join(maps_dir, "fond.png")
    fond_img = Image.open(fond_path).convert("RGBA") if os.path.exists(fond_path) else Image.new("RGBA", (2200, 1640), (240, 240, 240, 255))
    
    front_path = os.path.join(maps_dir, "frontieres_overlay.png")
    if os.path.exists(front_path):
        front_img = Image.open(front_path).convert("RGBA")
    else:
        front_img = Image.new("RGBA", (2200, 1640), (0, 0, 0, 0))

    tasks = []

    # 1. France Entière (Toutes les échéances horaires)
    france_dir = os.path.join(temp_root, "00_FRANCE_ENTIERE")
    for cat_name, layer_map in CATEGORIES_FRANCE.items():
        cat_dir = os.path.join(france_dir, cat_name)
        for layer_key, (clean_name, param_title, unit_str, (min_v, max_v)) in layer_map.items():
            src_layer = os.path.join(maps_dir, layer_key)
            if os.path.exists(src_layer):
                dst_layer = os.path.join(cat_dir, clean_name)
                os.makedirs(dst_layer, exist_ok=True)
                for f in os.listdir(src_layer):
                    base_name, ext = os.path.splitext(f)
                    if ext.lower() in [".webp", ".png"]:
                        src_f = os.path.join(src_layer, f)
                        lead_h = int(base_name) if base_name.isdigit() else 0
                        lbl_antenne, lbl_fichier, _ = get_local_datetime_info(run_dt, lead_h)
                        dst_f = os.path.join(dst_layer, f"{layer_key}_{lbl_fichier}_H{lead_h:02d}.webp")
                        tasks.append((src_f, dst_f, fond_img, front_img, None, (1100, 820), param_title, unit_str, min_v, max_v, lead_h, "France Entière", f"Run {run_hour_str}", lbl_antenne))

    # 2. Hauts-de-France (Classé en sous-dossiers propres, Toutes les échéances)
    hdf_dir = os.path.join(temp_root, "01_HAUTS_DE_FRANCE")
    for subfolder_name, (layer_key, param_title, unit_str, (min_v, max_v)) in CATEGORIES_HDF.items():
        src_layer = os.path.join(maps_dir, layer_key)
        if os.path.exists(src_layer):
            dst_layer = os.path.join(hdf_dir, subfolder_name)
            os.makedirs(dst_layer, exist_ok=True)
            for f in os.listdir(src_layer):
                base_name, ext = os.path.splitext(f)
                if ext.lower() in [".webp", ".png"]:
                    src_f = os.path.join(src_layer, f)
                    lead_h = int(base_name) if base_name.isdigit() else 0
                    lbl_antenne, lbl_fichier, _ = get_local_datetime_info(run_dt, lead_h)
                    dst_f = os.path.join(dst_layer, f"{layer_key}_{lbl_fichier}_H{lead_h:02d}.webp")
                    tasks.append((src_f, dst_f, fond_img, front_img, HDF_CROP, (800, 600), param_title, unit_str, min_v, max_v, lead_h, "Hauts-de-France", f"Run {run_hour_str}", lbl_antenne))

    # 3. Synthèses 24h
    synth_dir = os.path.join(temp_root, "02_SYNTHESES_24H")
    os.makedirs(synth_dir, exist_ok=True)
    for f in os.listdir(maps_dir):
        if "_24h_" in f and f.endswith((".webp", ".png")):
            base_name, _ = os.path.splitext(f)
            src_f = os.path.join(maps_dir, f)
            dst_f = os.path.join(synth_dir, f"{base_name}_{jour_run_nom}_{date_run_str}.webp")
            tasks.append((src_f, dst_f, fond_img, front_img, None, (1100, 820), "Synthèse Quotidienne 24h", "Max", 0, 100, 24, "France Entière", f"Run {run_hour_str}", date_run_str))

    print(f"🚀 Execution multi-thread de {len(tasks)} photos d'antenne HD (toutes échéances)...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(process_single_photo, tasks))
    
    img_count = sum(1 for r in results if r)

    # 4. README
    with open(os.path.join(temp_root, "LISEZ-MOI_INDEX.txt"), "w", encoding="utf-8") as rf:
        rf.write(README_INDEX_TEXT.format(date_str=f"{jour_run_nom} {date_run_str}", run_str=run_hour_str))

    # 5. Compression ZIP Niveau 9
    print(f"🗜️ Compression ZIP maximale vers {out_zip_name} ({img_count} photos WebP)...")
    with zipfile.ZipFile(out_zip_name, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(temp_root):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_root)
                zipf.write(file_path, arcname)

    try:
        shutil.rmtree(temp_root, ignore_errors=True)
    except Exception:
        pass

    zip_size_mb = os.path.getsize(out_zip_name) / (1024 * 1024)
    print(f"✅ Archive PHOTOS D'ANTENNE {out_zip_name} terminée : {zip_size_mb:.2f} Mo ({img_count} photos) !")
    return out_zip_name, zip_size_mb, img_count

if __name__ == "__main__":
    package_daily_archive(only_major_runs=False)
