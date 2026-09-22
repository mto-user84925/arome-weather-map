# Plan d'Action : Résolution des Problèmes Supabase et Archivage Quotidien

Le site rencontre des lenteurs extrêmes (timeouts) dues à une saturation du budget Disk IO de Supabase. Cela est principalement causé par le trigger `trg_sync_daily_summary` qui s'exécute des milliers de fois par heure.

## 📋 Analyse du Problème
1. **Trigger de synchro** : Chaque ligne insérée dans `observations_6mn` déclenche une mise à jour dans `daily_summaries`. Avec ~2000 stations, cela génère une pression constante sur les index.
2. **Taille des tables** : La table `observations_6mn` devient trop lourde pour un plan Free/Pro standard sans archivage agressif.
3. **Suggestion Utilisateur** : Créer un "dossier" par jour. Cela correspond à sortir les données brutes de la base relationnelle (DB) pour les mettre dans un stockage d'objets (Storage).

## 🚀 Solution Proposée

### Phase 1 : Allègement de la Pression (Immédiat)
1.  **Désactiver le Trigger** : Supprimer le trigger `trg_sync_daily_summary` sur `observations_6mn`.
2.  **Batch Processing** : Remplacer le trigger par une fonction planifiée (cron) qui agrège les données toutes les 15 ou 60 minutes. Cela réduit le nombre d'écritures de manière drastique.

### Phase 2 : Mise en place de l'Archivage par "Dossiers" (Journalier)
1.  **Nouveau Bucket Storage** : Créer un bucket `observations-archives`.
2.  **Fonction d'Archivage** : Développer une Edge Function `archive-daily-data` qui :
    -   Récupère toutes les données 6mn de la veille (`J-1`).
    -   Génère un fichier JSON structuré par station.
    -   Sauvegarde le fichier dans `archives/6mn/YYYY/MM/DD/data.json`.
    -   Supprime les données correspondantes de la table SQL `observations_6mn`.
3.  **Conservation SQL** : Ne garder que les 7 derniers jours en SQL pour les graphiques temps-réel. Pour l'historique ancien, le site lira le fichier JSON du jour concerné.

### Phase 3 : Optimisation du Frontend
1.  Modifier `MonthlyMapsHub.jsx` et `api.js` pour :
    -   Vérifier si les données sont en DB (récent).
    -   Si non, les récupérer depuis le JSON dans Storage (historique).

## 🛠️ Étapes Techniques
1.  [ ] Créer la migration SQL pour supprimer le trigger.
2.  [ ] Créer l'Edge Function `archive-daily-data`.
3.  [ ] Configurer le `cron.schedule` dans Supabase pour l'archivage nocturne.
4.  [ ] Mettre à jour `src/services/api.js` pour supporter la lecture depuis Storage.

---
> [!IMPORTANT]
> Cette approche permettra de rester sous les limites Disk IO tout en conservant un historique illimité via le stockage d'objets, beaucoup moins coûteux en ressources.
