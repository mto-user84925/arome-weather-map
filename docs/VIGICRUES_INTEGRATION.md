# 🌊 Intégration Vigicrues - Documentation

## 📋 Vue d'ensemble

L'onglet **"Rivières & Crues"** a été complètement refondu pour intégrer l'API officielle **Vigicrues** du gouvernement français. Cette intégration permet d'afficher en temps réel la vigilance crues sur l'ensemble du territoire français.

## ✨ Fonctionnalités implémentées

### 1. **Carte Interactive de France**
- Affichage de **337 tronçons de rivières** surveillés par Vigicrues
- Géométries précises des cours d'eau avec leurs tracés réels
- Couleurs selon le niveau de vigilance :
  - 🟢 **Vert** : Pas de vigilance particulière
  - 🟡 **Jaune** : Risque de crue ou de montée rapide des eaux
  - 🟠 **Orange** : Crue génératrice de débordements
  - 🔴 **Rouge** : Crue majeure

### 2. **Statistiques en temps réel**
- Compteur du nombre total de tronçons surveillés
- Badge d'alerte indiquant le nombre de tronçons en vigilance
- Répartition détaillée par niveau de vigilance (Vert/Jaune/Orange/Rouge)

### 3. **Interactions utilisateur**
- **Survol** : Épaississement du tronçon et affichage du nom
- **Clic** : Panneau d'information détaillée avec :
  - Nom du tronçon
  - Code du tronçon
  - Niveau de vigilance actuel
- **Mode plein écran** : Bouton pour agrandir la carte

### 4. **Légende détaillée**
- Explication de chaque niveau de vigilance
- Codes couleur conformes aux standards Vigicrues

## 🔧 Architecture technique

### Fichiers créés/modifiés

#### **Service API** (`src/services/vigicruuesService.js`)
Service complet pour interagir avec l'API Vigicrues :
- `fetchTronçonsGeoJSON()` : Récupère le GeoJSON avec toutes les géométries
- `fetchTronçons()` : Liste des tronçons
- `fetchStations()` : Liste des stations hydrométriques
- `fetchObservations(stationCode)` : Observations d'une station
- `fetchPrevisions(stationCode)` : Prévisions pour une station
- `calculateVigilanceStats(geoJSON)` : Calcul des statistiques

#### **Composant Carte** (`src/modules/crues/CruesMap.jsx`)
Carte interactive utilisant D3.js pour la projection géographique :
- Projection conique conforme (Lambert)
- Rendu SVG optimisé
- Gestion des états (loading, error, data)
- Interactions utilisateur

#### **Styles** (`src/modules/crues/CruesDashboard.css`)
Styles ajoutés :
- `.map-stats` : Statistiques en temps réel
- `.map-legend` : Légende détaillée
- `.troncon-info` : Panneau d'information
- `.alert-badge` : Badge d'alerte
- Animations et transitions

## 📊 API Vigicrues utilisée

### Endpoints principaux

1. **GeoJSON des tronçons** (utilisé actuellement)
   ```
   https://www.vigicrues.gouv.fr/services/1/InfoVigiCru.geojson
   ```
   - Contient 337 features (tronçons)
   - Géométries MultiLineString
   - Propriétés : NivInfViCr, lbentcru, CdEntCru, etc.

2. **Observations** (disponible pour extension future)
   ```
   https://www.vigicrues.gouv.fr/services/observations.json
   https://www.vigicrues.gouv.fr/services/observations.json?CdStationHydro=XXX
   ```

3. **Prévisions** (disponible pour extension future)
   ```
   https://www.vigicrues.gouv.fr/services/v1.1/prevision.json
   ```

4. **Stations** (disponible pour extension future)
   ```
   https://www.vigicrues.gouv.fr/services/v1.1/StaEntVigiCru.json
   ```

## 🎯 Données actuelles (exemple)

Au moment de l'implémentation :
- **337 tronçons** surveillés
- **15 tronçons en vigilance** :
  - 12 en jaune
  - 3 en orange
  - 0 en rouge
- **322 tronçons** sans vigilance (vert)

### Tronçons locaux (Nord)
- Lys amont - Laquette : Vert
- Lys plaine : Vert

## 🚀 Améliorations futures possibles

1. **Graphiques de hauteur d'eau**
   - Utiliser l'API observations pour afficher l'évolution du niveau
   - Graphiques interactifs avec Recharts

2. **Prévisions**
   - Afficher les prévisions de crue à 24h/48h
   - Timeline des risques

3. **Filtres**
   - Filtrer par niveau de vigilance
   - Filtrer par région/département
   - Recherche de tronçon

4. **Alertes personnalisées**
   - Notification si un tronçon local passe en vigilance
   - Abonnement à des tronçons spécifiques

5. **Données historiques**
   - Historique des crues
   - Statistiques annuelles

## 📱 Responsive

La carte est entièrement responsive :
- Adaptation automatique sur mobile
- Mode plein écran disponible
- Légende adaptative

## ⚡ Performance

- Chargement initial : ~1-2 secondes
- Rendu SVG optimisé pour 337 features
- Pas de re-rendu inutile grâce à `useMemo`

## 🔗 Ressources

- [Documentation API Vigicrues](https://www.vigicrues.gouv.fr/services/v1.1)
- [Site officiel Vigicrues](https://www.vigicrues.gouv.fr/)
- [Dictionnaire de données](https://id.eaufrance.fr/ddd/VIC/1.1)

## ✅ Tests

Script de test disponible : `scripts/test_vigicrues_simple.js`

```bash
node scripts/test_vigicrues_simple.js
```

Affiche :
- Nombre de tronçons
- Statistiques de vigilance
- Exemples de tronçons
- Tronçons locaux (Nord)
