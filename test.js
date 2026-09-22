const puppeteer = require('puppeteer');
(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text(), msg.location()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.toString(), err.stack));
    await page.goto('file://' + __dirname + '/index.html', { waitUntil: 'load' }); // wait for standard events, not network idle
    console.log("Page loaded. Generating click events...");
    await page.evaluate(() => {
        // Change region dropdown to trigger fetch
        const regionSelect = document.getElementById('region-select');
        if (regionSelect) {
            regionSelect.value = 'hdf';
            regionSelect.dispatchEvent(new Event('change'));
        }
    });

    await new Promise(r => setTimeout(r, 5000)); // Wait for fetch

    await browser.close();
})();
