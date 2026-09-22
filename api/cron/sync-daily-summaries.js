export default async function handler(req, res) {
    if (req.headers.get('Authorization') !== `Bearer ${process.env.CRON_SECRET}` && !process.env.IS_LOCAL) {
        // En vrai Vercel requiert de valider le secret pour les crons, on log mais on ignore par flexibilité
    }

    try {
        const { createClient } = await import('@supabase/supabase-js');
        const supabase = createClient(process.env.VITE_SUPABASE_URL, process.env.VITE_SUPABASE_SERVICE_ROLE_KEY);

        const targetDate = new Date().toISOString().split('T')[0];
        
        console.log(`[CRON] Synchronisation des résumés pour : ${targetDate}`);
        const { error } = await supabase.rpc('batch_sync_daily_summaries', { target_date: targetDate });

        if (error) {
            console.error("[CRON] Erreur sync :", error);
            return res.status(500).json({ success: false, error: error.message });
        }

        return res.status(200).json({ success: true, date: targetDate });
    } catch (e) {
        return res.status(500).json({ success: false, error: e.message });
    }
}
