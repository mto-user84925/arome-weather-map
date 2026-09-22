export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    
    try {
        const response = await fetch('https://vigilance.meteofrance.fr/fr', {
            headers: { 
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' 
            }
        });
        
        const setCookie = response.headers.get('set-cookie') || '';
        const match = setCookie.match(/mfsession=([^;]+)/);
        
        if (match) {
            const rawToken = decodeURIComponent(match[1]);
            const token = rawToken.replace(/[a-zA-Z]/g, c =>
                String.fromCharCode((c <= 'Z' ? 90 : 122) >= (c = c.charCodeAt(0) + 13) ? c : c - 26)
            );
            return res.status(200).json({ token, source: 'live' });
        }
        return res.status(500).json({ error: 'mfsession cookie not found in response' });
    } catch (e) {
        return res.status(500).json({ error: e.message });
    }
}
