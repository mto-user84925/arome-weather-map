const fs = require('fs');
const http = require('http');
const https = require('https');

// Read files from application meteociel
const stationsPath = '../applicaiton meteociel/src/data/stations_index.json';
const namesPath = '../applicaiton meteociel/src/data/stationNames.json';
const rankStationsPath = '../applicaiton meteociel/src/data/rankStations.json';
const rankNameToIdPath = '../applicaiton meteociel/src/data/rankNameToId.json';
const recordsPath = '../applicaiton meteociel/src/data/global_daily_records.json';

const stationsIndex = JSON.parse(fs.readFileSync(stationsPath, 'utf8'));
const stationNamesData = JSON.parse(fs.readFileSync(namesPath, 'utf8'));
const rankStationsData = JSON.parse(fs.readFileSync(rankStationsPath, 'utf8'));
const rankNameToIdData = JSON.parse(fs.readFileSync(rankNameToIdPath, 'utf8'));
const globalRecords = JSON.parse(fs.readFileSync(recordsPath, 'utf8'));

// Filter HDF stations (exclude 02 because it has lambert coords, or convert them if necessary, but we only have lat/lon for 59, 62, 80, 60)
// The user usually uses 59, 62, 80, 60 for HDF map. Wait, 02 is Aisne. Let's include it if it has valid lat/lon, but stations_index has 700000+ lat for Aisne.
// Actually, earlier we only had 59, 62, 80, 60 mapped accurately. Let's keep 59, 62, 80, 60.
const hdfDepts = ['59', '62', '80', '60', '02'];
const hdfStations = stationsIndex.filter(s => hdfDepts.includes(s.dept));

const STATION_TO_ID = Object.entries(stationNamesData).reduce((acc, [id, name]) => {
    acc[name.toUpperCase()] = id;
    return acc;
}, {});

const METEOCIEL_ID_MAP = Object.entries(rankStationsData).reduce((acc, [id, name]) => {
    acc[name] = id;
    return acc;
}, {});

const OFFICIAL_ID_MAP = rankNameToIdData;

async function fetchHtml(url) {
    return new Promise((resolve, reject) => {
        const client = url.startsWith('https') ? https : http;
        client.get(url, (res) => {
            let data = [];
            res.on('data', chunk => data.push(chunk));
            res.on('end', () => {
                const buffer = Buffer.concat(data);
                // Meteociel is windows-1252, but Buffer to string might be ok for numbers
                resolve(buffer.toString('latin1'));
            });
        }).on('error', reject);
    });
}

function parseRanking(html) {
    const results = [];
    const regex = /<tr>(.*?)<\/tr>/gs;
    let match;
    while ((match = regex.exec(html)) !== null) {
        const row = match[1];
        if (!row.includes('(') || !row.includes(')')) continue;
        if (row.includes('<table')) continue;

        const cells = [];
        const cellRegex = /<td.*?>(.*?)<\/td>/gs;
        let cMatch;
        while ((cMatch = cellRegex.exec(row)) !== null) {
            cells.push(cMatch[1].replace(/<[^>]+>/g, '').trim());
        }

        if (cells.length < 2) continue;

        let nameIndex = cells.findIndex(c => c.includes('(') && c.includes(')'));
        if (nameIndex === -1) continue;

        const stationFull = cells[nameIndex];
        const smatch = stationFull.match(/^(.*)\s\((.*)\)$/);
        const station = smatch ? smatch[1].trim() : stationFull;
        const dept = smatch ? smatch[2].trim() : '';

        // value
        let valStr = (cells[nameIndex + 1] || cells[cells.length - 1]);
        valStr = valStr.replace(/[^\d.-]/g, '').replace(',', '.');
        const value = parseFloat(valStr);

        let foundId = OFFICIAL_ID_MAP[stationFull] || STATION_TO_ID[station.toUpperCase()] || METEOCIEL_ID_MAP[stationFull];
        if (foundId && /^\d+$/.test(foundId.toString())) {
            let idStr = foundId.toString();
            if (idStr.length === 7 && idStr[0] !== '0') {
                idStr = '0' + idStr;
            }
            foundId = idStr;
        }

        if (foundId && !isNaN(value)) {
            results.push({ poste: foundId, station, value });
        }
    }
    return results;
}

async function getDayRankings(day, month, year) {
    const modes = [
        { key: 'tx', modeId: '25' },
        { key: 'tn', modeId: '26' },
        { key: 'fxi', modeId: '27' },
        { key: 'rr', modeId: '28' },
    ];
    const stationMap = new Map();

    for (const { key, modeId } of modes) {
        const url = `https://www.meteociel.fr/obs/classement.php?archive=1&ua=1&all=1&mode=${modeId}&pays=&ud=0&dec=0&alt=0&u2=1&ma=0&jour=${day}&mois=${month}&annee=${year}&sub=OK`;
        try {
            const html = await fetchHtml(url);
            const results = parseRanking(html);
            for (const r of results) {
                if (!stationMap.has(r.poste)) {
                    stationMap.set(r.poste, { poste: r.poste, station: r.station, tx: null, tn: null, fxi: null, rr: null });
                }
                const record = stationMap.get(r.poste);
                if (key === 'fxi') {
                    record[key] = parseFloat((r.value * 0.27778).toFixed(1)); // km/h to m/s
                } else {
                    record[key] = r.value;
                }
            }
        } catch (e) {
            console.error('Error fetching mode', modeId, e);
        }
    }
    return stationMap;
}

async function run() {
    const now = new Date();
    // Force UTC timezone to avoid local inconsistencies, then convert to Europe/Paris? Wait, just use local since user is in France.
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const day = now.getDate();

    console.log(`Fetching observations for ${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}...`);
    const obsMap = await getDayRankings(day, month, year);

    const mm_dd = `${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
    const historical = globalRecords[mm_dd] || {};

    const brokenRecords = [];

    for (const st of hdfStations) {
        const obs = obsMap.get(st.id);
        if (!obs) continue; // no data today

        const rec = historical[st.id] || {};

        const beaten = [];

        if (obs.tx !== null && rec.tx && obs.tx > rec.tx.val) {
            beaten.push({ type: 'tx', val: obs.tx, oldVal: rec.tx.val, oldYear: rec.tx.year });
        }
        if (obs.tn !== null && rec.tn && obs.tn < rec.tn.val) {
            beaten.push({ type: 'tn', val: obs.tn, oldVal: rec.tn.val, oldYear: rec.tn.year });
        }
        if (obs.rr !== null && rec.rr && obs.rr > rec.rr.val) {
            beaten.push({ type: 'rr', val: obs.rr, oldVal: rec.rr.val, oldYear: rec.rr.year });
        }
        if (obs.fxi !== null && rec.fxi && obs.fxi > rec.fxi.val) { // Though fxi records usually sparse
            beaten.push({ type: 'fxi', val: (obs.fxi * 3.6).toFixed(1), oldVal: (rec.fxi.val * 3.6).toFixed(1), oldYear: rec.fxi.year });
        }

        if (beaten.length > 0) {
            brokenRecords.push({
                id: st.id,
                name: st.name,
                lat: st.lat,
                lon: st.lon,
                dept: st.dept,
                records: beaten
            });
        }
    }

    const outputContent = `const todayRecordsHDF = ${JSON.stringify(brokenRecords, null, 2)};`;
    fs.writeFileSync('today_hdf_records.js', outputContent);
    console.log(`Generated today_hdf_records.js with ${brokenRecords.length} broken records.`);
}

run();
