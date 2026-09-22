import { Resend } from 'resend';

// Clé chargée depuis les variables d'environnement Vercel (jamais en dur dans le code)
const resend = new Resend(process.env.RESEND_API_KEY);

export default async function handler(req, res) {
    const { secret } = req.query;
    if (secret !== 'meteo-alert-secure-token-2026') {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { station, value, time, to_email } = req.body;

    if (!to_email) {
        return res.status(400).json({ error: 'Missing to_email' });
    }

    // Détection du type d'alerte "intelligente" basée sur l'unité ou la clé (simplifié ici car on reçoit la valeur brute)
    // On va essayer de deviner le contexte ou l'ajouter dans le body depuis le SQL si on veut être parfait.
    // Pour l'instant, faisons un template générique mais joli.

    // Formatage Heure
    const dateStr = new Date(time).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
    const timeStr = new Date(time).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

    try {
        const data = await resend.emails.send({
            from: 'Meteo Alert <onboarding@resend.dev>',
            to: [to_email],
            subject: `🚨 ALERTE MÉTÉO à ${station}`,
            html: `
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; padding: 40px 0;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                
                <!-- En-tête -->
                <div style="background-color: #ef4444; padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 24px; text-transform: uppercase; letter-spacing: 1px;">Alerte Seuil Dépassé</h1>
                </div>

                <!-- Contenu -->
                <div style="padding: 40px 30px;">
                    <p style="font-size: 16px; color: #374151; margin-bottom: 30px; line-height: 1.5;">
                        Une observation récente a déclenché l'une de vos alertes configurées.
                        Voici les détails du relevé :
                    </p>

                    <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px; border: 1px solid #e5e7eb;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Station</td>
                                <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">${station}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb;">Valeur Relevée</td>
                                <td style="padding: 8px 0; color: #ef4444; font-weight: 800; font-size: 18px; text-align: right; border-top: 1px solid #e5e7eb;">${value}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb;">Date & Heure</td>
                                <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right; border-top: 1px solid #e5e7eb;">${dateStr} à ${timeStr}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin-top: 40px;">
                        <a href="https://minisite-douai.vercel.app/" style="background-color: #111827; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">Voir les détails sur le site</a>
                    </div>
                </div>

                <!-- Pied de page -->
                <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                        Cet email a été envoyé automatiquement par votre Minisite Météo.<br>
                        Vous pouvez gérer vos alertes depuis la section "Alertes" du site.
                    </p>
                </div>

            </div>
        </body>
        </html>
      `,
        });

        return res.status(200).json(data);
    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: error.message });
    }
}
