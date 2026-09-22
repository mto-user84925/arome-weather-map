import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
    process.env.SUPABASE_URL || 'https://ubdevaemtwbzxksjlhjg.supabase.co',
    process.env.SUPABASE_SERVICE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViZGV2YWVtdHdienhrc2psaGpnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODc2NTA2OCwiZXhwIjoyMDg0MzQxMDY4fQ.RC_D6wljCTi1WEf0aG3QoEf1ZH_sJkP9TiVXXAovMzI'
);

export const config = {
    runtime: 'edge',
};

export default async function handler(request) {
    // Vérifier l'autorisation (Vercel envoie un header spécifique pour les crons)
    const authHeader = request.headers.get('authorization');
    if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
        // En dev ou si pas de secret, on continue quand même
        console.log('⚠️ Cron secret non vérifié');
    }

    try {
        // Récupérer les données foudre d'hier via l'API Agate
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const dateStr = yesterday.toISOString().split('T')[0].replace(/-/g, '');
        const displayDate = yesterday.toISOString().split('T')[0];

        console.log(`📅 Archivage foudre pour ${displayDate}`);

        // Récupérer les données Agate
        const agateUrl = `https://www.mwattest.fr/ORAGE/orage/ws/wsOragesGMaps.php?date=${dateStr}&heureD=00&heureF=23&pass=jh2kH3,R`;
        const agateRes = await fetch(agateUrl);
        const agateData = await agateRes.json();

        if (!Array.isArray(agateData)) {
            return new Response(JSON.stringify({ error: 'Invalid Agate data' }), { status: 500 });
        }

        const impactCount = agateData.length;
        console.log(`⚡ ${impactCount} impacts trouvés`);

        // Synchroniser vers Supabase
        if (impactCount > 0) {
            const strikesToInsert = agateData.map(s => ({
                strike_time: `${s.date.replace(/\//g, '-')}T${s.heure}+01:00`,
                lat: parseFloat(s.lat),
                lon: parseFloat(s.lon)
            }));

            // Insérer par chunks de 500
            for (let i = 0; i < strikesToInsert.length; i += 500) {
                const chunk = strikesToInsert.slice(i, i + 500);
                await supabase.from('lightning_strikes').upsert(chunk, {
                    onConflict: 'strike_time,lat,lon',
                    ignoreDuplicates: true
                });
            }
        }

        // Enregistrer le bilan (sans image pour l'instant - l'image sera générée côté client)
        await supabase.from('foudre_bilans').upsert({
            date: displayDate,
            image_url: null, // Pas d'image côté serveur
            impact_count: impactCount,
            captured_at: new Date().toISOString()
        }, { onConflict: 'date' });

        return new Response(JSON.stringify({
            success: true,
            date: displayDate,
            impacts: impactCount,
            message: `✅ ${impactCount} impacts archivés pour ${displayDate}`
        }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
        });

    } catch (error) {
        console.error('❌ Erreur:', error);
        return new Response(JSON.stringify({ error: error.message }), { status: 500 });
    }
}
