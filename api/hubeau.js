import { Resend } from 'resend';

export default async function handler(req, res) {
    const { type, station_code, code_entite } = req.query;

    try {
        let url = '';
        if (type === 'stations') {
            // Find stations near a point or for a river
            url = `https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations?size=50`;
            if (code_entite) url += `&code_entite_hydro=${code_entite}`;
        } else if (type === 'obs') {
            // Get latest observations for a station
            url = `https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_station=${station_code}&size=100&sort=desc`;
        } else {
            return res.status(400).json({ error: 'Invalid type' });
        }

        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        });

        if (!response.ok) {
            throw new Error(`HubEau responded with ${response.status}`);
        }

        const data = await response.json();
        return res.status(200).json(data);
    } catch (error) {
        console.error('HubEau Proxy Error:', error);
        return res.status(500).json({ error: error.message });
    }
}
