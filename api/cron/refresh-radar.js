/**
 * Vercel Cron API Route: Refresh Météo-France Radar
 * 
 * Downloads radar HDF5 package from MF API,
 * converts to PNG with official color palette,
 * uploads to Supabase Storage.
 * 
 * Triggered every 5 minutes by Vercel Cron.
 */
import { createClient } from '@supabase/supabase-js';
import { gunzipSync } from 'zlib';
import { PNG } from 'pngjs';
import { writeFileSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

// ============================================================
// Config
// ============================================================
const MF_API_KEY = process.env.MF_RADAR_API_KEY || process.env.VITE_METEO_RADAR_TOKEN || '';
const SUPABASE_URL = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL || '';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
const BUCKET = 'radar-mf';
const ARCHIVE_BUCKET = 'radar-archive';
const MAX_FRAMES = 288; // 24h * 12 frames/h

// Météo-France precipitation color palette (mm/h)
const RAIN_PALETTE = [
    [0.0, 0.1, 0, 0, 0, 0], [0.1, 0.15, 4, 4, 132, 200], [0.15, 0.2, 4, 20, 156, 210],
    [0.2, 0.3, 4, 40, 180, 215], [0.3, 0.4, 4, 64, 204, 220], [0.4, 0.5, 4, 88, 220, 220],
    [0.5, 0.6, 4, 112, 236, 225], [0.6, 0.9, 4, 140, 252, 225], [0.9, 1.2, 20, 168, 220, 225],
    [1.2, 1.5, 8, 180, 8, 230], [1.5, 2.0, 24, 200, 24, 230], [2.0, 2.7, 60, 216, 60, 230],
    [2.7, 3.7, 100, 232, 100, 230], [3.7, 4.8, 180, 232, 20, 235], [4.8, 6.0, 232, 232, 4, 235],
    [6.0, 8.0, 252, 216, 4, 235], [8.0, 12.0, 252, 176, 4, 240], [12.0, 16.0, 252, 132, 4, 240],
    [16.0, 27.0, 252, 88, 4, 240], [27.0, 37.0, 252, 36, 4, 245], [37.0, 48.0, 220, 4, 4, 245],
    [48.0, 65.0, 188, 4, 4, 245], [65.0, 85.0, 176, 4, 100, 250], [85.0, 120.0, 160, 4, 160, 250],
    [120.0, 150.0, 176, 44, 200, 250], [150.0, 210.0, 200, 80, 220, 250],
    [210.0, 278.0, 220, 120, 240, 250], [278.0, 370.0, 236, 160, 248, 250],
    [370.0, 486.0, 248, 200, 252, 250], [486.0, 9999, 255, 240, 255, 255],
];

// ============================================================
// Supabase helpers
// ============================================================
function getSupabase() {
    return createClient(SUPABASE_URL, SUPABASE_KEY, {
        auth: { persistSession: false }
    });
}

// Ensure bucket exists (generic)
async function ensureBucket(supabase, bucketName) {
    const { data } = await supabase.storage.getBucket(bucketName);
    if (!data) {
        await supabase.storage.createBucket(bucketName, {
            public: true,
            fileSizeLimit: 5 * 1024 * 1024,
            allowedMimeTypes: ['image/png', 'application/json']
        });
        console.log('Created bucket', bucketName);
    }
}

async function getExistingManifest(supabase) {
    try {
        const { data } = supabase.storage.from(BUCKET).getPublicUrl('manifest.json');
        const res = await fetch(data.publicUrl + '?t=' + Date.now());
        if (res.ok) return await res.json();
    } catch (e) { /* no manifest yet */ }
    return null;
}

// ============================================================
// Download & extract
// ============================================================
async function downloadRadarPackage() {
    console.log('[1/4] Downloading radar package...');
    const res = await fetch('https://public-api.meteofrance.fr/public/DPPaquetRadar/v1/mosaique/paquet', {
        headers: { 'apikey': MF_API_KEY, 'Accept': 'application/gzip' }
    });
    if (!res.ok) throw new Error('MF API error: ' + res.status);
    const buffer = Buffer.from(await res.arrayBuffer());
    console.log('  Downloaded ' + buffer.length + ' bytes');
    return buffer;
}

function extractH5Files(gzipData) {
    console.log('[2/4] Extracting HDF5 files...');
    const decompressed = gunzipSync(gzipData);
    const h5Files = {};
    let offset = 0;

    while (offset < decompressed.length - 512) {
        // TAR header: name is at offset 0, 100 bytes, NUL-terminated
        const nameBytes = decompressed.subarray(offset, offset + 100);
        const nulIndex = nameBytes.indexOf(0);
        const nameRaw = nameBytes.subarray(0, nulIndex !== -1 ? nulIndex : 100).toString('utf8').trim();

        if (!nameRaw) break;

        // TAR header: size is at offset 124, 12 bytes, octal string
        const sizeStr = decompressed.subarray(offset + 124, offset + 136).toString('utf8').split('\0')[0].trim();
        const size = sizeStr ? parseInt(sizeStr, 8) : 0;

        // Focus on composite radar data (IPRN)
        // Check for IPRN anywhere in the name as the path might vary
        if (!nameRaw.startsWith('././@') && nameRaw.includes('IPRN') && nameRaw.endsWith('.h5')) {
            const data = Buffer.from(decompressed.subarray(offset + 512, offset + 512 + size));
            const parts = nameRaw.replace('.h5', '').split('_');
            const tsStr = parts[parts.length - 1];
            h5Files[tsStr] = data;
            console.log('  Found: ' + nameRaw + ' -> ' + tsStr + ' (' + size + ' bytes)');
        }

        offset += 512 + Math.ceil(size / 512) * 512;
    }
    return h5Files;
}

// ============================================================
// HDF5 -> PNG conversion
// ============================================================
async function parseH5Radar(h5wasm, buffer) {
    const tmpFileName = 'radar_tmp.h5';

    try {
        h5wasm.FS.writeFile(tmpFileName, buffer);
        const f = new h5wasm.File(tmpFileName, 'r');

        const dataDS = f.get('dataset1/data1/data');
        const rawData = dataDS.value;
        const shape = dataDS.shape;

        const what = f.get('dataset1/data1/what');
        const gain = what.attrs['gain']?.value ?? 0.01;
        const offsetVal = what.attrs['offset']?.value ?? 0.0;
        const nodata = what.attrs['nodata']?.value ?? 65535;
        const undetect = what.attrs['undetect']?.value ?? 65534;

        const where = f.get('where');
        const bounds = {
            UL_lat: where.attrs['UL_lat']?.value ?? 53.67,
            UL_lon: where.attrs['UL_lon']?.value ?? -9.965,
            UR_lat: where.attrs['UR_lat']?.value ?? 52.55,
            UR_lon: where.attrs['UR_lon']?.value ?? 17.56,
            LL_lat: where.attrs['LL_lat']?.value ?? 38.14,
            LL_lon: where.attrs['LL_lon']?.value ?? -6.72,
            LR_lat: where.attrs['LR_lat']?.value ?? 37.46,
            LR_lon: where.attrs['LR_lon']?.value ?? 11.98,
        };
        const xsize = where.attrs['xsize']?.value ?? 3472;
        const ysize = where.attrs['ysize']?.value ?? 3472;

        f.close();
        return { rawData, shape: [ysize, xsize], gain, offset: offsetVal, nodata, undetect, bounds };
    } finally {
        try { h5wasm.FS.unlink(tmpFileName); } catch (e) { }
    }
}

async function h5ToPngBuffer(h5wasm, h5Data, timestampStr) {
    const { rawData, shape, gain, offset, nodata, undetect, bounds } = await parseH5Radar(h5wasm, h5Data);
    const [ysize, xsize] = shape;

    // Downscale 4x for High Definition (868x868)
    // 4x provides a good balance between zoom precision and processing speed
    const scale = 4;
    const hNew = Math.floor(ysize / scale);
    const wNew = Math.floor(xsize / scale);

    const png = new PNG({ width: wNew, height: hNew });

    for (let y = 0; y < hNew; y++) {
        for (let x = 0; x < wNew; x++) {
            let sum = 0, validCount = 0;

            for (let dy = 0; dy < scale; dy++) {
                for (let dx = 0; dx < scale; dx++) {
                    const raw = rawData[(y * scale + dy) * xsize + (x * scale + dx)];
                    if (raw !== nodata && raw !== undetect) {
                        sum += raw * gain + offset;
                        validCount++;
                    }
                }
            }

            const idx = (y * wNew + x) * 4;
            if (validCount === 0) {
                png.data[idx] = png.data[idx + 1] = png.data[idx + 2] = png.data[idx + 3] = 0;
                continue;
            }

            const mmh = (sum / validCount) * 12.0;
            let r = 0, g = 0, b = 0, a = 0;
            for (const [minV, maxV, pr, pg, pb, pa] of RAIN_PALETTE) {
                if (mmh >= minV && mmh < maxV) { r = pr; g = pg; b = pb; a = pa; break; }
            }
            png.data[idx] = r; png.data[idx + 1] = g; png.data[idx + 2] = b; png.data[idx + 3] = a;
        }
    }

    const pngBuffer = PNG.sync.write(png, { colorType: 6, filterType: 4 });
    console.log('  Processed: radar_' + timestampStr + '.png (' + wNew + 'x' + hNew + ', ' + Math.round(pngBuffer.length / 1024) + 'KB)');
    return { pngBuffer, bounds, size: [wNew, hNew] };
}

// ============================================================
// Main handler
// ============================================================
export default async function handler(req, res) {
    const startTime = Date.now();

    try {
        if (!MF_API_KEY) throw new Error('MF_RADAR_API_KEY not configured');
        if (!SUPABASE_URL || !SUPABASE_KEY) throw new Error('Supabase not configured');

        const supabase = getSupabase();
        // Ensure both buckets exist
        await ensureBucket(supabase, BUCKET);
        await ensureBucket(supabase, ARCHIVE_BUCKET);

        // Get existing manifest
        const existingManifest = await getExistingManifest(supabase);
        const existingTimestamps = new Set(
            (existingManifest?.frames || []).map(f => f.timestamp)
        );

        // PARALLELIZE: Start h5wasm init while downloading
        const h5WasmPromise = (async () => {
            const mod = await import('h5wasm');
            await mod.ready;
            return mod;
        })();

        // Download & extract
        const pkg = await downloadRadarPackage();
        const h5Files = extractH5Files(pkg);
        if (Object.keys(h5Files).length === 0) throw new Error('No HDF5 files in package');

        // Process only NEW frames
        console.log('[3/4] Converting & uploading new frames...');

        // Wait for h5wasm ready
        const h5wasm = await h5WasmPromise;

        const allFrames = {};
        for (const frame of (existingManifest?.frames || [])) {
            allFrames[frame.timestamp] = frame;
        }

        let newCount = 0;
        let latestBounds = {};

        // Sort files to process oldest first
        const sortedFiles = Object.entries(h5Files).sort();

        for (const [tsStr, h5Data] of sortedFiles) {
            if (existingTimestamps.has(tsStr)) {
                console.log('  Skipping (exists): ' + tsStr);
                continue;
            }

            // STRICT LIMIT: Only process 2 new frames max per run to avoid timeout
            if (newCount >= 2) {
                console.log('  Time limit safety: Stopping after 2 frames.');
                break;
            }

            const { pngBuffer, bounds, size } = await h5ToPngBuffer(h5wasm, h5Data, tsStr);
            latestBounds = bounds;

            const filename = 'radar_' + tsStr + '.png';

            // Upload to LIVE bucket
            const { error } = await supabase.storage
                .from(BUCKET)
                .upload(filename, pngBuffer, { contentType: 'image/png', upsert: true, cacheControl: '300' });

            if (error) { console.error('  Upload error:', error.message); continue; }

            // Upload to ARCHIVE bucket (if XXh00)
            if (tsStr.endsWith('0000')) {
                const year = tsStr.substring(0, 4);
                const month = tsStr.substring(4, 6);
                const archivePath = year + '/' + month + '/radar_' + tsStr + '.png';
                await supabase.storage.from(ARCHIVE_BUCKET).upload(archivePath, pngBuffer, {
                    contentType: 'image/png', upsert: true
                });
                console.log('  Archived: ' + archivePath);
            }

            allFrames[tsStr] = { filename, timestamp: tsStr, bounds, size };
            newCount++;
        }

        // Cleanup old frames (keep 24h)
        console.log('[4/4] Updating manifest...');
        const sortedKeys = Object.keys(allFrames).sort();
        if (sortedKeys.length > MAX_FRAMES) {
            const toRemove = sortedKeys.slice(0, sortedKeys.length - MAX_FRAMES);
            for (const oldTs of toRemove) {
                await supabase.storage.from(BUCKET).remove([allFrames[oldTs].filename]);
                delete allFrames[oldTs];
            }
        }

        // Build & upload manifest
        const finalFrames = Object.keys(allFrames).sort().map(k => allFrames[k]);
        if (finalFrames.length > 0 && !Object.keys(latestBounds).length) {
            latestBounds = finalFrames[finalFrames.length - 1].bounds || {};
        }

        const { data: urlData } = supabase.storage.from(BUCKET).getPublicUrl('');

        const manifest = {
            generated_at: new Date().toISOString(),
            source: 'Meteo-France DPPaquetRadar/v1',
            storage: 'supabase',
            base_url: urlData.publicUrl,
            bounds: latestBounds,
            leaflet_bounds: Object.keys(latestBounds).length ? [
                [latestBounds.LL_lat || 38.14, latestBounds.UL_lon || -9.965],
                [latestBounds.UL_lat || 53.67, latestBounds.UR_lon || 17.56]
            ] : [],
            frame_count: finalFrames.length,
            frames: finalFrames
        };

        const { error: mError } = await supabase.storage
            .from(BUCKET)
            .upload('manifest.json', Buffer.from(JSON.stringify(manifest, null, 2)), {
                contentType: 'application/json', upsert: true, cacheControl: '60'
            });
        if (mError) throw new Error('Manifest upload failed: ' + mError.message);

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        console.log('[OK] Done in ' + elapsed + 's: ' + newCount + ' new, ' + finalFrames.length + ' total');

        return res.status(200).json({
            success: true, new_frames: newCount,
            total_frames: finalFrames.length, elapsed_seconds: parseFloat(elapsed)
        });

    } catch (error) {
        console.error('Radar refresh error:', error);
        return res.status(500).json({ error: error.message });
    }
}

export const config = { maxDuration: 60 };
