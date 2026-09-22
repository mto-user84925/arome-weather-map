const fs = require('fs');
const data = JSON.parse(fs.readFileSync('records_utf8.json', 'utf8'));

const months = {
    'janvier': 0, 'février': 1, 'mars': 2, 'avril': 3, 'mai': 4, 'juin': 5,
    'juillet': 6, 'août': 7, 'septembre': 8, 'octobre': 9, 'novembre': 10, 'décembre': 11
};

const records = {};

for (const row of data) {
    const date = row.Date;
    if (!date || !date.match(/^\d+ \w+$/)) continue;
    const parts = date.split(' ');
    const day = parseInt(parts[0]);
    const month = months[parts[1].toLowerCase()];
    if (month === undefined || isNaN(day)) continue;
    const key = `${month + 1}-${day}`;
    records[key] = { min: parseFloat(row.Max), year: row.Min };
}

const output = `const lilleRecordsMin = ${JSON.stringify(records)};`;
fs.writeFileSync('lille_records.js', output, 'utf8');
console.log(`Exported ${Object.keys(records).length} records`);
