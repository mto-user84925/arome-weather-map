const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const rx = /getElementById\(['"]([^'"]*)['"]\)(?:\?|)\.checked/g;
let m;
while ((m = rx.exec(html)) !== null) {
    const id = m[1];
    if (!html.includes('id=\"' + id + '\"') && !html.includes('id=\'' + id + '\'')) {
        console.log('MISSING CHECKBOX ID:', id);
    }
}
