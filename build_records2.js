const fs = require('fs');
const raw = fs.readFileSync('records2.json', 'utf8').replace(/^\uFEFF/, '');
const data = JSON.parse(raw);

const months = {
    'janvier': 1, 'f\xE9vrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'ao\xFBt': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'd\xE9cembre': 12
};

const rec = {};
for (const r of data) {
    if (!r.Date || !r.Date.match(/^\d+ \w+$/)) continue;
    const parts = r.Date.split(' ');
    const day = parseInt(parts[0]);
    const mKey = parts[1] ? parts[1].toLowerCase() : '';
    const m = months[mKey];
    if (!m || isNaN(day)) continue;
    rec[m + '-' + day] = { min: parseFloat(r.Max), year: r.Min };
}

const output = 'const lilleRecordsMin = ' + JSON.stringify(rec) + ';';
fs.writeFileSync('lille_records.js', output, 'utf8');
console.log('Total records:', Object.keys(rec).length);
