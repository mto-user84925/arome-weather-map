import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import https from 'https'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'serve-local-meteo-models',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url.startsWith('/local-meteo-models/')) {
            const relativePath = decodeURIComponent(req.url.replace('/local-meteo-models/', '').split('?')[0]);
            const filePath = path.join(__dirname, 'data/output', relativePath);
            if (fs.existsSync(filePath)) {
              res.setHeader('Content-Type', 'image/png');
              res.setHeader('Cache-Control', 'no-store, must-revalidate');
              res.end(fs.readFileSync(filePath));
              return;
            } else {
              // Fallback transparent : si le fichier n'est pas local, on le charge depuis la Supabase de prod !
              const remoteUrl = `https://ubdevaemtwbzxksjlhjg.supabase.co/storage/v1/object/public/meteo-models/${relativePath}`;
              https.get(remoteUrl, (remoteRes) => {
                if (remoteRes.statusCode === 200) {
                  res.setHeader('Content-Type', 'image/png');
                  remoteRes.pipe(res);
                } else {
                  next();
                }
              }).on('error', () => {
                next();
              });
              return;
            }
          }
          next();
        });
      }
    }
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-leaflet': ['leaflet', 'react-leaflet'],
          'vendor-charts': ['recharts'],
          'vendor-d3': ['d3-delaunay', 'd3-geo', 'd3-scale'],
          'vendor-pdf': ['jspdf', 'jspdf-autotable'],
          'vendor-supabase': ['@supabase/supabase-js'],
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api-meteo': {
        target: 'https://public-api.meteofrance.fr/public/DPObs/v1',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-meteo/, ''),
        secure: false,
      },
      '/api-meteo-paquet': {
        target: 'https://public-api.meteofrance.fr/public/DPPaquetObs/v1',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-meteo-paquet/, ''),
        secure: false,
      },
      '/api-meteo-poste': {
        target: 'https://public-api.meteofrance.fr/public/DPAI01/v1',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-meteo-poste/, ''),
        secure: false,
      },
      '/mf-token': {
        target: 'https://portail-api.meteofrance.fr/token',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mf-token/, ''),
        secure: false,
      },
      '/api-agate': {
        target: 'https://www.mwattest.fr',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-agate/, ''),
        secure: false,
      },
      '/ORAGE': {
        target: 'https://www.mwattest.fr',
        changeOrigin: true,
        secure: false,
      },
      '/api-radar-mf': {
        target: 'https://public-api.meteofrance.fr/public/DPPaquetRadar/v1',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-radar-mf/, ''),
        secure: false,
      },
      '/api-meteociel': {
        target: 'https://www.meteociel.fr',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-meteociel/, ''),
        secure: false,
      }
    }
  }
})
