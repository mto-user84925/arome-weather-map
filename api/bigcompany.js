import path from 'path';
import fs from 'fs';

const MONTHS_EN = ['january','february','march','april','may','june','july','august','september','october','november','december'];
const JOURS_FR = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche'];

// Mapping picto Météo-France (p1…p30) → appellations officielles flux RSS
// Source : mergeMFIntoBase dans dist/index.html (logique conservée à l'identique)
// "Soleil voilé" (p2, p3) → nuageux, comme demandé
const PICTO_MF = {
    p1:  'soleil',      // Ensoleillé / Ciel clair
    p2:  'eclaircies',  // Peu nuageux / Eclaircies
    p3:  'nuageux',     // Voilé
    p4:  'nuageux',     // Ciel voilé (= soleil voilé → nuageux)
    p5:  'nuageux',     // Nuageux
    p6:  'couvert',     // Couvert
    p7:  'pluieforte',  // Pluies fortes
    p8:  'brouillard',  // Brouillard
    p9:  'averse',      // Averses
    p10: 'orages',      // Orages
    p11: 'orages',      // Orages forts
    p12: 'orages',      // Orages violents
    p13: 'pluie',       // Pluies et averses
    p14: 'pluie',       // Pluies
    p15: 'orages',      // Orages avec pluie
    p16: 'neige',       // Neige
    p17: 'orages',      // Orages neigeants
    p26: 'grele',       // Grêle
    p27: 'grele',       // Averses de grêle
    p28: 'forteneige',  // Fortes chutes de neige
    p29: 'forteneige',  // Fortes chutes de neige
    p30: 'eclaircies',  // Éclaircies
};

function parsePicto(s) {
    if (!s) return 'eclaircies';
    // Normalise : "p2j" → "p2", "p12bis" → "p12", casse ignorée
    const key = s.toLowerCase().replace(/[jn]$/, '').replace('bis', '');
    return PICTO_MF[key] ?? 'eclaircies';
}

// Chargement des saints depuis saints.json
let saintsData = {};
try {
    const saintsPath = path.join(process.cwd(), 'saints.json');
    if (fs.existsSync(saintsPath)) saintsData = JSON.parse(fs.readFileSync(saintsPath, 'utf8'));
} catch (e) { console.error('Erreur chargement saints.json:', e); }

function getSaint(dateObj) {
    const month = MONTHS_EN[dateObj.getMonth()];
    const dayIdx = dateObj.getDate() - 1;
    const list = saintsData[month] || [];
    if (dayIdx < list.length) {
        const item = list[dayIdx];
        const name = item[0] || '';
        const prefix = item[1] || '';
        if (prefix === 'Saint') return `St ${name}`;
        if (prefix === 'Sainte') return `Ste ${name}`;
        if (prefix) return `${prefix} ${name}`.trim();
        return name;
    }
    return 'St Météo';
}

// Récupère le token Météo-France via /api/token, puis fallback meteofrance_token.json
async function getMFToken(baseUrl) {
    try {
        const r = await fetch(`${baseUrl}/api/token`);
        if (r.ok) { const d = await r.json(); if (d.token) return d.token; }
    } catch (_) {}
    try {
        const r = await fetch(`${baseUrl}/meteofrance_token.json?t=${Date.now()}`);
        if (r.ok) { const d = await r.json(); if (d.token) return d.token; }
    } catch (_) {}
    return null;
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/rss+xml; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');

    const lat  = req.query.lat  ? parseFloat(req.query.lat)                          : 45.76;
    const lon  = req.query.lon  ? parseFloat(req.query.lon)                          : 4.84;
    const days = req.query.days ? Math.min(15, Math.max(1, parseInt(req.query.days))): 7;
    const BASE = 'https://europe-1-v2.vercel.app';

    try {
        // 1. Token Météo-France (Token 0 : récupéré depuis le site lui-même)
        const token = await getMFToken(BASE);
        if (!token) throw new Error('Service météo temporairement indisponible');

        // 2. Appel API prévisions (server-side, non exposé au client)
        const mfUrl = `https://rwg.meteofrance.com/internet2018client/2.0/forecast?lat=${lat}&lon=${lon}&token=${token}&_=${Date.now()}`;
        const mfRes = await fetch(mfUrl, {
            headers: { 'User-Agent': 'MeteoClimatPro-Europe1/1.0' }
        });
        if (!mfRes.ok) throw new Error(`Données météo indisponibles (${mfRes.status})`);
        const mfData = await mfRes.json();

        const props      = mfData.properties || {};
        const hourlyMF   = props.forecast        || [];   // J0–J3 horaire
        const dailyMF    = props.daily_forecast  || [];   // J0–J14 journalier

        if (!dailyMF.length) throw new Error('Aucune donnée journalière Météo-France');

        // 3. Construction des items RSS depuis daily_forecast
        const now = new Date();
        let itemsXml = '';

        for (let i = 0; i < Math.min(days, dailyMF.length); i++) {
            const df = dailyMF[i];

            // Date du jour (format YYYY-MM-DD dans daily_forecast.time ou .dt)
            const dateStr = (df.time || df.dt || '').slice(0, 10);
            if (!dateStr) continue;

            const dt = new Date(`${dateStr}T12:00:00+02:00`);
            const tMin = df.T_min != null ? Math.round(parseFloat(df.T_min)) : '';
            const tMax = df.T_max != null ? Math.round(parseFloat(df.T_max)) : '';
            const temps = parsePicto(df.daily_weather_icon);

            let dateNom;
            if      (i === 0) dateNom = "Aujourd'hui";
            else if (i === 1) dateNom = 'Demain';
            else if (i === 2) dateNom = 'Après-demain';
            else              dateNom = JOURS_FR[(dt.getDay() + 6) % 7];

            itemsXml +=
                `\t\t<item>\n` +
                `\t\t\t<date>${dateStr}</date>\n` +
                `\t\t\t<date_nom>${dateNom}</date_nom>\n` +
                `\t\t\t<saint>${getSaint(dt)}</saint>\n` +
                `\t\t\t<temp_min>${tMin}</temp_min>\n` +
                `\t\t\t<temp_max>${tMax}</temp_max>\n` +
                `\t\t\t<temps>${temps}</temps>\n` +
                `\t\t</item>\n`;
        }

        const xml =
            `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n` +
            `<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n` +
            `\t<channel>\n` +
            `\t\t<title>Météo-Climat Pro - Météo</title>\n` +
            `\t\t<link>https://europe-1-v2.vercel.app/rss/bigcompany.php</link>\n` +
            `\t\t<description>Météo - Météo-Climat Pro</description>\n` +
            `\t\t<language>fr</language>\n` +
            `\t\t<lastBuildDate>${now.toUTCString()}</lastBuildDate>\n` +
            `\t\t<copyright>copyright ${now.getFullYear()} - Météo-Climat Pro</copyright>\n` +
            `\t\t<atom:link href="https://europe-1-v2.vercel.app/rss/bigcompany.php" rel="self" type="application/rss+xml"/>\n` +
            itemsXml +
            `\t</channel>\n` +
            `</rss>\n`;

        return res.status(200).send(xml);

    } catch (err) {
        console.error('Erreur génération flux RSS:', err.message);
        return res.status(500).send(
            `<?xml version="1.0" encoding="UTF-8"?><error>Service temporairement indisponible</error>`
        );
    }
}
