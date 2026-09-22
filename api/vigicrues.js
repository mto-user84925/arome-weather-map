export default async function handler(req, res) {
    const { type } = req.query;

    // List of possible Vigicrues endpoints to try as fallbacks
    const endpoints = {
        'troncons': [
            'https://www.vigicrues.gouv.fr/services/troncons.json.php',
            'https://www.vigicrues.gouv.fr/services/troncons.geojson',
            'https://api.vigicrues.gouv.fr/api/v1/vigilance/troncons.json'
        ],
        'vigilance': [
            'https://www.vigicrues.gouv.fr/services/vigilance.json.php',
            'https://www.vigicrues.gouv.fr/services/vigilance.geojson'
        ]
    };

    const targetEndpoints = endpoints[type] || [];

    for (const url of targetEndpoints) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.vigicrues.gouv.fr/'
                },
                next: { revalidate: 300 } // Cache for 5 minutes
            });

            if (response.ok) {
                const data = await response.json();
                return res.status(200).json(data);
            }
        } catch (error) {
            console.error(`Failed to fetch from ${url}:`, error);
        }
    }

    return res.status(404).json({ error: 'Data not found on any Vigicrues endpoint', type });
}
