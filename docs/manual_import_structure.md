# Structure du fichier CSV pour import manuel (observations_6mn)

Voici la structure du fichier CSV que vos outils devraient générer si vous souhaitez combler les lacunes manuellement dans la table `observations_6mn` de Supabase.

### 📋 En-têtes du fichier (Header)
`station_id,timestamp,t,u,td,ff,fxi,pres,rr_per,dd,vv`

### 📝 Détail des colonnes
| Colonne | Type | Description | Exemple |
|---|---|---|---|
| **station_id** | Texte | Identifiant INSEE de la station (8 chiffres) | `59178001` |
| **timestamp** | ISO8601 | Horodatage au format UTC (ISO 8601) | `2026-03-07T12:00:00Z` |
| **t** | Nombre | Température de l'air (°C) | `12.5` |
| **u** | Nombre | Humidité relative (%) | `75` |
| **td** | Nombre | Point de rosée (°C) | `8.2` |
| **ff** | Nombre | Vitesse moyenne du vent (km/h) | `15` |
| **fxi** | Nombre | Rafale maximale (km/h) | `32` |
| **pres** | Nombre | Pression atmosphérique au niveau de la mer (hPa) | `1013.2` |
| **rr_per** | Nombre | Précipitations sur la période (mm) | `0.2` |
| **dd** | Nombre | Direction du vent (degrés) | `270` |
| **vv** | Nombre | Visibilité horizontale (m) | `10000` |

### 🛠️ Comment l'importer dans Supabase
1. Accédez à votre tableau de bord [Supabase](https://ubdevaemtwbzxksjlhjg.supabase.co).
2. Allez dans l'onglet **Table Editor**.
3. Sélectionnez la table `observations_6mn`.
4. Cliquez sur **Import Data**.
5. Glissez votre fichier CSV.
6. Cliquez sur **Import**.
