export const config = {
    runtime: 'edge',
};

export default async function handler(request) {
    // Vérification optionnelle du secret cron de Vercel (si configuré)
    const authHeader = request.headers.get('authorization');
    if (process.env.CRON_SECRET && authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
        console.warn('⚠️ Cron secret non vérifié ou manquant');
    }

    const SUPABASE_URL = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
    const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

    if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
        return new Response(JSON.stringify({ error: 'Missing Supabase environment variables' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }

    console.log("📡 Déclenchement de la synchro Vigilance depuis Vercel...");

    try {
        const response = await fetch(`${SUPABASE_URL}/functions/v1/collect-vigilance`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        return new Response(JSON.stringify({
            success: response.ok,
            data,
            source: 'vercel-cron'
        }), {
            status: response.status,
            headers: { 'Content-Type': 'application/json' }
        });

    } catch (error) {
        console.error('❌ Erreur synchro vigilance Vercel:', error);
        return new Response(JSON.stringify({ error: error.message }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}
