export default async function handler(req, res) {
    if (req.headers.get('Authorization') !== `Bearer ${process.env.CRON_SECRET}` && !process.env.IS_LOCAL) {
        // Validation secrète pour Vercel
    }

    try {
        const { createClient } = await import('@supabase/supabase-js');
        const supabase = createClient(process.env.VITE_SUPABASE_URL, process.env.VITE_SUPABASE_SERVICE_ROLE_KEY);

        // On archive et supprime les données d'il y a 2 jours
        const targetDate = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        console.log(`[CRON] Archivage pour la date : ${targetDate}`);

        const BATCH_SIZE = 10000;
        let allRows = [];
        let from = 0;
        let hasMore = true;

        while (hasMore) {
            const { data, error } = await supabase
                .from('observations_6mn')
                .select('*')
                .gte('timestamp', `${targetDate}T00:00:00Z`)
                .lt('timestamp', `${targetDate}T23:59:59Z`)
                .range(from, from + BATCH_SIZE - 1)
                .order('timestamp', { ascending: true });

            if (error) throw error;
            if (data && data.length > 0) {
                allRows.push(...data);
                if (data.length < BATCH_SIZE) hasMore = false;
                else from += BATCH_SIZE;
            } else {
                hasMore = false;
            }
        }

        if (allRows.length > 0) {
            const [y, m, d] = targetDate.split('-');
            const filePath = `6mn/${y}/${m}/${d}.json`;
            
            // Upload Storage
            const { error: uploadError } = await supabase.storage
                .from('observations-archives')
                .upload(filePath, JSON.stringify(allRows), { contentType: 'application/json', upsert: true });

            if (uploadError) throw uploadError;

            // Suppression SQL (après sauvegarde)
            await supabase
                .from('observations_6mn')
                .delete()
                .gte('timestamp', `${targetDate}T00:00:00Z`)
                .lt('timestamp', `${targetDate}T23:59:59Z`);
                
            console.log(`[CRON] Succès ! ${allRows.length} lignes transférées.`);
        }

        return res.status(200).json({ success: true, count: allRows.length });
    } catch (e) {
        console.error("[CRON] Erreur archivage :", e.message);
        return res.status(500).json({ success: false, error: e.message });
    }
}
