# 🔎 AUDIT & FINALISATION — Carte Météo Multi-Modèles HD (Météo-Climat Pro)

> Rapport d'audit + brief de reprise. Les correctifs décrits ci-dessous ont été
> **appliqués** sur les fichiers listés en §5. Les points « à faire » (§6) sont
> destinés à la poursuite du développement (ex. Antigravity).

---

## 1. Résumé exécutif

L'application est fonctionnelle et bien structurée (WebGL + Canvas 2D + SVG,
manifestes par modèle, pipeline Python). L'audit a toutefois révélé **plusieurs
bugs critiques**, dont un qui contredit directement l'objectif n°1 du projet :

| # | Sévérité | Constat | Statut |
|---|----------|---------|--------|
| 1 | 🔴 Critique | **GFS affiche des copies AROME** (indépendance des modèles violée) | Code corrigé + purge à faire |
| 2 | 🔴 Critique | **La sonde au survol est totalement inopérante** (aucune valeur ne s'affiche) | ✅ Corrigé |
| 3 | 🟠 Majeur | **La légende ne reflète pas les couleurs/valeurs réelles** des cartes | ✅ Corrigé |
| 4 | 🟠 Majeur | **L'export « HD » capture l'écran zoomé** (pas du 2200×1640 broadcast) | ✅ Corrigé |
| 5 | 🟠 Majeur | **AROME `vent` == `rafales`** (même fichier, deux grandeurs différentes) | À régénérer |
| 6 | 🟠 Majeur | **ARPEGE absent du pipeline CI/CD** (aucun runner) | ✅ Runner ajouté |
| 7 | 🟡 Mineur | `js/palettes.js`, `css/style.css`, `js/app.js`… non chargés (code mort) | Documenté |
| 8 | 🟡 Mineur | Fichiers orphelins (ARPEGE 51 tuiles temp. vs 35 échéances) | À nettoyer |

---

## 2. Preuves (empreintes MD5)

Comparaison des dalles `temperature/000.webp` entre modèles :

```
arome   D4F9B9A9071A76AC71770157C5CB0378
gfs     D4F9B9A9071A76AC71770157C5CB0378   ← identique à AROME ❌
ecmwf   (différent)                          ✅ données natives
arpege  52EF4F906E21EE2BDAA2D37293BB7163     ✅ données natives
icon    41A698C79B1B56F603BC351DC8CE2AE4     ✅ données natives
```

Le même test sur `vent`, `pluie_1h`, `pression`, `mucape`, `rafales` donne
`gfs == arome` pour **toutes** les couches testées → **GFS est intégralement une
copie d'AROME** dans l'état actuel du dépôt.

Vent vs rafales AROME :

```
vent    (000.webp)  8C324C7510AA02965EC6E48C6A2C6AC8
rafales (000.webp)  8C324C7510AA02965EC6E48C6A2C6AC8   ← identique ❌
```

---

## 3. Cause racine des bugs de données

### 3.1 GFS = copie AROME

`setup_multimodels.py` copiait **les dalles AROME** (`output/maps/*`) dans les
dossiers `gfs`, `ecmwf`, `arpege`, `icon` puis fabriquait un `index.json` en
renommant simplement `model_name`. Tant que `run_gfs()` n'écrase pas ces dalles
(échec silencieux du téléchargement NOMADS), **le site affiche les prévisions
AROME sous l'étiquette GFS**.

### 3.2 Sonde au survol inopérante

- Les manifests ne déclarent **ni `stops`** (couleurs de palette) **ni `probes`**
  (grilles binaires de valeurs).
- `valueFromColour()` retournait donc toujours `null` → la sonde restait masquée.

### 3.3 AROME vent == rafales

Dans `fetch_and_render_all.py`, `vent` et `rafales` utilisent le **même style WMS
`FF__HEIGHT__SHADING`** (paramètres distincts mais rendu identique côté serveur),
d'où des fichiers identiques.

---

## 4. Corrections appliquées

### 4.1 Front-end

- **`js/palettes.js`** — réécrit comme **source unique de vérité** : 22 couches,
  stops `{value, color}` identiques au `PALETTES` Python, `transparent_below`,
  `unit`, `decimals`, `label`. Expose `window.WEATHER_PALETTES`,
  `getLayerPalette`, `paletteGradientCSS`, `paletteTicks`.
- **`js/arome-map.js`**
  - `applyPaletteStops()` injecte `stops`/`transparent_below`/`decimals` dans les
    couches du manifest au chargement et à chaque changement de modèle →
    **la sonde au survol/au clic fonctionne** (inversion couleur→valeur, préfixe `≈`).
  - Légende : dégradé **exact** (positions proportionnelles aux valeurs) + **5
    repères chiffrés réels** calculés, au lieu de gradients codés en dur.
  - Export PNG : **plein cadre natif 2200×1640** (fond météo + frontières +
    cartouche Modèle • Paramètre • Validité • Météo-Climat Pro), indépendant du zoom.
  - `switchModel` : chemin AROME standardisé sur `output/arome`, mise à jour de
    `data-base-url`/`data-model`, injection des stops, rollback propre en cas d'échec.
  - Chemin du masque rendu relatif (`resolvePath('maps/mask_france.png')`).
- **`index.html`** — `data-base-url="output/arome"`, ajout `data-model`, chargement
  de `js/palettes.js` **avant** `js/arome-map.js`.

### 4.2 Pipeline Python

- **`setup_multimodels.py`** — ne copie **plus aucune dalle météo** entre modèles.
  Il ne fait que créer la structure + copier les assets géographiques partagés
  (fond, frontières, communes, masque). → supprime la source du bug « fausse data ».
- **`pipeline/fetch_and_render_all.py`**
  - `_fetch_arome_tile` généralisé en `_fetch_mf_tile(wms_url, …)`.
  - **Ajout de `run_arpege()`** (H+00..H+102, pas de 3h) + enregistrement dans
    `RUNNERS` et dans `--model`. Endpoint ARPEGE surchargeable via `ARPEGE_WMS_URL`.
  - **GFS `vent`** : calcul du module `√(UGRD² + VGRD²) × 3.6` (au lieu du seul U).
  - **ECMWF `vent`** : calcul du module `√(10u² + 10v²) × 3.6` (au lieu du seul 10u),
    avec repli documenté sur `10u`.

---

## 5. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `index.html` | base-url, data-model, chargement palettes.js |
| `js/palettes.js` | réécrit (source unique 22 palettes) |
| `js/arome-map.js` | sonde, légende, export HD, switchModel |
| `setup_multimodels.py` | suppression de la copie croisée de données |
| `pipeline/fetch_and_render_all.py` | runner ARPEGE + vent GFS/ECMWF correct |

Vérifications passées : `node --check` (2 JS) ✅, `python -m py_compile` (2 py) ✅.

---

## 6. À FAIRE (reprise Antigravity / CI) — par priorité

### P0 — Purger les fausses données GFS (obligatoire)

Les dalles AROME-copies sont **encore présentes** dans `output/gfs`. Le code ne
les recrée plus, mais il faut les supprimer/regénérer :

```bash
# 1) Supprimer les dalles météo GFS (dossiers de couches), en gardant les assets partagés
for d in output/gfs/maps/*/; do rm -rf "$d"; done

# 2) Regénérer GFS (nécessite accès NOMADS + cfgrib dans le runner CI)
python pipeline/fetch_and_render_all.py --model gfs

# 3) Vérifier que GFS n'est plus identique à AROME
md5sum output/gfs/maps/temperature/000.webp output/arome/maps/temperature/000.webp
#    (les deux empreintes DOIVENT différer)
```

> ⚠️ Si `run_gfs()` ne peut pas télécharger NOMADS, **ne pas commiter** de manifest
> GFS : le front-end affichera « modèle non disponible » au lieu de fausses données.

### P1 — Régénérer AROME vent ≠ rafales

Rejouer `--model arome` puis vérifier `output/arome/maps/vent/000.webp` ≠
`output/arome/maps/rafales/000.webp`. Si toujours identiques, le style WMS
`FF__HEIGHT__SHADING` doit être distingué (style rafales dédié).

### P2 — Confirmer l'endpoint ARPEGE WMS

`ARPEGE_WMS` utilise la convention `MF-NWP-GLOBAL-ARPEGE-001-EURAT5-WMS`.
À valider dans la doc Météo-France (Confluence « Documentation APIs ») ; sinon
définir `ARPEGE_WMS_URL` dans les secrets GitHub Actions.

### P3 — Robustesse du manifeste (ne pas référencer de tuiles manquantes)

Aujourd'hui `write_manifest()` référence les 22 couches × toutes les échéances,
même si le téléchargement a échoué (tuiles absentes → images cassées). Améliorer
`write_manifest` pour ne référencer que les `.webp` réellement présents sur disque.

### P4 — Nettoyer les tuiles orphelines

ARPEGE a 51 tuiles `temperature` pour 35 échéances (restes d'un pas horaire).
Ajouter un nettoyage des `%03d.webp` non référencés par le manifeste après chaque run.

### P5 — Champs dérivés non-natifs (transparence à documenter)

Dans `run_gfs` / `run_ecmwf`, plusieurs couches sont mappées sur le « meilleur
champ disponible » et ne sont donc **pas physiquement natives** :
- `reflectivite`, `graupel`, `neige*` → `APCP`/`tp` (précipitation totale) ;
- `humidex`, `temperature_ressentie` → température ;
- ECMWF `rafales`/`rafales_cumul` → `10u` (pas de rafale en opendata gratuit).

Décision produit à prendre : masquer ces couches pour GFS/ECMWF (honnêteté) ou les
garder en les étiquetant « approximation ».

### P6 — Code mort

`js/app.js`, `js/engine.js`, `js/manifest.js`, `js/multimodel.js`, `js/regions.js`,
`css/style.css` ne sont pas chargés par `index.html`. À supprimer ou à intégrer.

---

## 7. Architecture de référence (rappel)

```
index.html                         → interface (sélecteurs, légende, timeline)
js/palettes.js                     → palettes (source unique, 22 couches)
js/arome-map.js                    → moteur WebGL/Canvas (zoom, sonde, export)
output/{modele}/maps/index.json    → manifeste (métadonnées + échéances)
output/{modele}/maps/{param}/{step}.webp   → dalles 2200×1640
pipeline/fetch_and_render_all.py   → téléchargement GRIB2/WMS → WebP
.github/workflows/update_models.yml → cron 3h → pipeline → GitHub Pages
```

**Règle d'or** : une dalle météo ne peut provenir que du fetcher de **son propre
modèle**. Jamais de copie inter-modèle.
