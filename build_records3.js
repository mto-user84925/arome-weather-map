const fs = require('fs');
const raw = fs.readFileSync('records2.json', 'utf8').replace(/\uFEFF/, '').trim();
const d = JSON.parse(raw);

const months = {
    'janvier': 1, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12
};

function normalize(s) {
    return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() : s.toLowerCase();
}

const rec = {};
for (const r of d) {
    if (!r.Date) continue;
    const txt = normalize(r.Date).trim();
    const m = txt.match(/^(\d+) (\w+)$/);
    if (!m) continue;
    const day = parseInt(m[1]);
    const mon = months[m[2]];
    if (!mon || isNaN(day)) continue;
    rec[mon + '-' + day] = { min: parseFloat(r.Max), year: r.Min };
}

console.log('Total:', Object.keys(rec).length);
const output = 'const lilleRecordsMin = ' + JSON.stringify(rec) + ';';
fs.writeFileSync('lille_records.js', output, 'utf8');
