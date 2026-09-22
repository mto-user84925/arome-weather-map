#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_fond_arome.py — Fonds de carte, masque et frontières (par domaine)
==========================================================================
Utilise la SOURCE UNIQUE des domaines (pipeline/domains.py) : les fonds sont
donc parfaitement alignés avec les dalles météo (fini le décalage de ~170 px).
Usage : python pipeline/generate_fond_arome.py --domain france|antilles|reunion|all
"""
import os
import sys
import json
import math
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "pipeline"))
from domains import DOMAINS, Domain, mercator_y  # noqa: E402


def project(domain_obj, lon, lat):
    return domain_obj.project(lon, lat)


def iter_rings(geom):
    t = geom["type"]
    if t == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring


def polygon_path(rings, d):
    parts = []
    for ring in rings:
        pts = [project(d, p[0], p[1]) for p in ring]
        if len(pts) < 3:
            continue
        d_ = "M%.1f %.1f " % pts[0] + "L" + \
            " ".join("%.1f %.1f" % p for p in pts[1:]) + "Z"
        parts.append(d_)
    return " ".join(parts)


def line_to_svg(geom, d):
    if geom is None or geom.is_empty:
        return ""
    if geom.geom_type == "LineString":
        pts = [project(d, p[0], p[1]) for p in geom.coords]
        if len(pts) < 2:
            return ""
        return "M%.1f %.1f L%s" % (pts[0][0], pts[0][1],
                                   " ".join("%.1f %.1f" % p for p in pts[1:]))
    if geom.geom_type == "MultiLineString":
        return " ".join(line_to_svg(g, d) for g in geom.geoms if not g.is_empty)
    return ""


def load_json(name):
    path = os.path.join(BASE_DIR, "config", name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


import shapely.geometry  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OCEAN = (143, 163, 184)
LAND = (237, 234, 226)
BORDER = (160, 165, 170)
NATURAL = "#0b1220"   # côtes / frontières nationales (noir franc)
DEPT = "#7a828e"      # départements (gris fin)
LAND_FRANCE = (232, 228, 218)  # France légèrement distincte


def generate(domain):
    dom = Domain(domain)
    W, H = dom.width, dom.height
    if domain == "antilles":
        out_dirs = [os.path.join(BASE_DIR, "output", "arome_antilles", "maps")]
    elif domain == "reunion":
        out_dirs = [os.path.join(BASE_DIR, "output", "arome_reunion", "maps")]
    else:
        out_dirs = [os.path.join(BASE_DIR, "output", "arome", "maps")]
    for d in out_dirs:
        os.makedirs(d, exist_ok=True)
    out_dir = out_dirs[0]
    print("Fond %s : %s (lon %g..%g, lat %g..%g, %dx%d, proj: %s)"
          % (domain, dom.name, dom.west, dom.east, dom.south,
             dom.north, W, H, dom.projection), flush=True)

    countries = load_json("countries-50m.geojson")
    boundaries = load_json("international-boundaries.geojson")
    coastlines = load_json("coastlines.geojson")
    depts = load_json("departements.geojson")

    # 1) fond.webp + mask_france.png (masque des TERRES)
    im = Image.new("RGB", (W, H), OCEAN)
    draw = ImageDraw.Draw(im)
    im_mask = Image.new("L", (W, H), 0)
    draw_mask = ImageDraw.Draw(im_mask)

    def draw_feat(rings, color, mask_val):
        for ring in rings:
            pts = [project(dom, p[0], p[1]) for p in ring]
            if len(pts) >= 3:
                draw.polygon(pts, fill=color)
                if mask_val:
                    draw_mask.polygon(pts, fill=mask_val)

    # Terres émergées
    for feat in countries.get("features", []):
        geom = feat.get("geometry")
        if not geom:
            continue
        props = feat.get("properties") or {}
        is_fr = props.get("ISO_A2") == "FR" or props.get("ADMIN") == "France"
        color = LAND_FRANCE if is_fr else LAND
        draw_feat(iter_rings(geom), color, 255)

    for feat in depts.get("features", []):
        geom = feat.get("geometry")
        if geom:
            draw_feat(iter_rings(geom), LAND_FRANCE, 255)

    for d in out_dirs:
        im.save(os.path.join(d, "fond.webp"), format="WEBP", quality=85)
        im_mask.save(os.path.join(d, "mask_france.png"), format="PNG", optimize=True)

    # 2) frontieres.svg
    bounds_box = shapely.geometry.box(dom.west, dom.south, dom.east, dom.north)
    france_shapes = []
    depts_d = []
    for feat in depts.get("features", []):
        geom = feat.get("geometry")
        if not geom:
            continue
        s = shapely.geometry.shape(geom)
        if not s.intersects(bounds_box):
            continue
        france_shapes.append(s)
        depts_d.append(polygon_path(iter_rings(geom), dom))

    france_union = unary_union(france_shapes) if france_shapes else shapely.geometry.Polygon()
    france_mask = france_union.buffer(0.015) if not france_union.is_empty else shapely.geometry.Polygon()

    def extract_lines(collection):
        out = []
        for feat in collection.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            s = shapely.geometry.shape(geom)
            if not s.intersects(bounds_box):
                continue
            cleaned = s.intersection(bounds_box).difference(france_mask)
            if cleaned.is_empty:
                continue
            if cleaned.geom_type == "LineString":
                d_ = line_to_svg(cleaned, dom)
                if d_:
                    out.append(d_)
            elif cleaned.geom_type == "MultiLineString":
                for ls in cleaned.geoms:
                    d_ = line_to_svg(ls, dom)
                    if d_:
                        out.append(d_)
        return " ".join(p for p in out if p)

    foreign_boundaries_d = extract_lines(boundaries)
    foreign_coastlines_d = extract_lines(coastlines)
    france_border_d = line_to_svg(france_union.boundary, dom)
    national_lines = (foreign_boundaries_d + " " + foreign_coastlines_d
                      + " " + france_border_d).strip()
    depts_combined = " ".join(depts_d)

    if domain == "france":
        nat_stroke = "#000000"
        nat_width = "2.4"
        dept_stroke = "#000000"
        dept_width = "1.2"
        dept_opacity = "0.95"
    else:
        nat_stroke = NATURAL
        nat_width = "1.8"
        dept_stroke = DEPT
        dept_width = "0.8"
        dept_opacity = "0.85"

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'width="%d" height="%d">\n'
        '<!-- Côtes et frontières nationales -->\n'
        '<path d="%s" fill="none" stroke="%s" stroke-width="%s" '
        'stroke-linejoin="round" stroke-linecap="round"/>\n'
        '<!-- Départements français -->\n'
        '<path d="%s" fill="none" stroke="%s" stroke-width="%s" '
        'stroke-opacity="%s" stroke-linejoin="round" '
        'stroke-linecap="round"/>\n'
        '</svg>\n' % (W, H, W, H, national_lines, nat_stroke, nat_width,
                      depts_combined, dept_stroke, dept_width, dept_opacity)
    )
    for d in out_dirs:
        with open(os.path.join(d, "frontieres.svg"), "w",
                  encoding="utf-8") as f:
            f.write(svg)
        print("✅ %s : fond.webp, mask_france.png, frontieres.svg générés dans %s"
              % (domain, d), flush=True)

    # 3) Extraction et projection des villes dans communes.json
    places = []
    w, e, s, n = dom.west, dom.east, dom.south, dom.north
    if domain in ("antilles", "reunion"):
        cities_om = load_json("cities_om.json")
        for c in cities_om:
            try:
                lat, lon = float(c[2]), float(c[3])
                if w <= lon <= e and s <= lat <= n:
                    places.append(c)
            except Exception:
                continue
    else:
        communes = load_json("communes-compact.json")
        if isinstance(communes, list):
            places = communes

    for d in out_dirs:
        with open(os.path.join(d, "communes.json"), "w", encoding="utf-8") as f:
            json.dump(places, f, ensure_ascii=False)
        print("✅ %s : communes.json (%d lieux)" % (domain, len(places)), flush=True)


def main():
    ap = argparse.ArgumentParser(description="Fonds de carte par domaine")
    ap.add_argument("--domain", default="france")
    args = ap.parse_args()
    if args.domain == "all":
        for dom in ["france", "antilles", "reunion"]:
            generate(dom)
    else:
        generate(args.domain)


if __name__ == "__main__":
    main()