#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_arome_maps.py — Point d'entrée AROME HD 0,01° (1,3 km)
================================================================
Ce script ne produit PLUS de données synthétiques.

Historique (à ne pas réintroduire) : la version précédente appelait
`generate_synthetic_arome_field()`, qui fabriquait des champs à partir de
sinusoïdes et publiait ces images sous le nom de « Cartes AROME HD
officielles Météo-France ». C'était une violation directe de la règle d'or
n°4 (honnêteté physique des données) : aucune valeur affichée ne provenait
du modèle.

Il délègue désormais au moteur réel `pipeline/arome_open_data.py`, qui :
  1. sélectionne le dernier run AROME complet sur le S3 open data
     Météo-France (HP1 / SP1 / SP2 / SP3, 0,01°) ;
  2. décode les GRIB2 avec eccodes ;
  3. calcule les champs physiques (cumuls horaires par différence,
     réflectivité directe du modèle, altitude SP3…) ;
  4. reprojette en Mercator 2200×1640 sur les bornes de `domains.py` ;
  5. écrit les dalles WebP, les sondes HKV1 et le manifeste index.json.

Usage :
    python generate_arome_maps.py                 # run le plus récent, H+00 → H+51
    python generate_arome_maps.py --max-hours 24  # tronqué à H+24
    python generate_arome_maps.py --fail-if-empty # code retour 1 si rien produit
"""
import os
import sys
import time
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(BASE_DIR, "pipeline")
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)


def _check_dependencies():
    """Vérifie les dépendances avant de lancer un run long."""
    missing = []
    for mod in ("numpy", "PIL", "requests", "scipy"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    try:
        import eccodes  # noqa: F401
    except ImportError:
        missing.append("eccodes")
    if missing:
        print("❌ Dépendances manquantes : %s" % ", ".join(missing))
        print("   pip install -r requirements.txt")
        return False
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Génération des cartes AROME HD 0,01° depuis les GRIB2 "
                    "open data Météo-France (aucune donnée synthétique).")
    ap.add_argument("--max-hours", type=int, default=51,
                    help="Échéance maximale en heures (défaut 51)")
    ap.add_argument("--fail-if-empty", action="store_true",
                    help="Code retour 1 si aucune échéance n'a pu être rendue")
    args = ap.parse_args()

    print("=" * 70)
    print("🛰️  AROME HD 0,01° (1,3 km) — GRIB2 open data Météo-France")
    print("=" * 70)

    if not _check_dependencies():
        return 2

    import arome_open_data  # noqa: E402

    t0 = time.time()
    print("📅 Sélection du run et téléchargement des paquets en cours…")
    arome_open_data.run(max_hours=args.max_hours)

    manifest = os.path.join(BASE_DIR, "output", "arome", "maps", "index.json")
    print("\n" + "=" * 70)
    if os.path.exists(manifest):
        print("✅ Cartes AROME HD générées en %.1f min" % ((time.time() - t0) / 60.0))
        print("📄 Manifeste : %s" % manifest)
        print("=" * 70)
        return 0

    print("❌ Aucun manifeste produit : le run n'a rendu aucune échéance.")
    print("   Vérifier l'accès au bucket open data Météo-France.")
    print("=" * 70)
    return 1 if args.fail_if_empty else 0


if __name__ == "__main__":
    sys.exit(main())
