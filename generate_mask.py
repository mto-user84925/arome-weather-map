#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur du Masque Officiel France & Corse (2200x1640)
=======================================================
Génère une texture de masque ultra-précise (France = 255, Extérieur = 0)
projetée en EPSG:3857 (38°N-57°N, -12°W-18°E) pour découper parfaitement
les calques météo et ne conserver QUE la France métropolitaine et la Corse.
"""

import os
import json
import urllib.request
import numpy as np
from PIL import Image, ImageDraw

WIDTH = 2200
HEIGHT = 1640

# Bornes EPSG:3857 AROME HD
SOUTH = 38.0
NORTH = 57.0
WEST = -12.0
EAST = 18.0

def latlon_to_xy(lat, lon):
    # Transformation Mercator EPSG:3857
    x = (lon - WEST) / (EAST - WEST) * WIDTH
    
    # Formule Mercator Y
    lat_rad = np.radians(lat)
    n_rad = np.radians(NORTH)
    s_rad = np.radians(SOUTH)
    
    y_m = np.log(np.tan(np.pi / 4 + lat_rad / 2))
    y_n = np.log(np.tan(np.pi / 4 + n_rad / 2))
    y_s = np.log(np.tan(np.pi / 4 + s_rad / 2))
    
    y = (1.0 - (y_m - y_s) / (y_n - y_s)) * HEIGHT
    return float(x), float(y)


def generate_france_mask():
    print("🇫🇷 Téléchargement du contour officiel des départements français...")
    url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
    try:
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
    except Exception as e:
        print(f"Erreur téléchargement: {e}")
        return

    img = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(img)

    print("🎨 Tracé du masque haute précision pour la France et la Corse...")
    for feature in data.get("features", []):
        geom = feature.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        if gtype == "Polygon":
            for ring in coords:
                pts = [latlon_to_xy(pt[1], pt[0]) for pt in ring]
                draw.polygon(pts, fill=255)
        elif gtype == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    pts = [latlon_to_xy(pt[1], pt[0]) for pt in ring]
                    draw.polygon(pts, fill=255)

    # Sauvegarde du masque dans output/maps/mask_france.png
    out_path = "C:/Users/grego/Desktop/arome-weather-map/output/maps/mask_france.png"
    img.save(out_path, format="PNG")
    
    # Copie également dans scratch
    scratch_path = "C:/Users/grego/.gemini/antigravity/scratch/arome-weather-map/output/maps/mask_france.png"
    os.makedirs(os.path.dirname(scratch_path), exist_ok=True)
    img.save(scratch_path, format="PNG")

    print(f"✅ Masque France généré avec succès : {out_path}")


if __name__ == "__main__":
    generate_france_mask()
