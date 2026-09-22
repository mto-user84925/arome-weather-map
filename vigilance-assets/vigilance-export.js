/* ============================================================================
   Vigilance — Téléchargement PNG « comme les cartes AROME HD »
   2200×1640, cartouche haut gauche (titre + modèle + date), logo haut droite,
   légende en bas centrée, encart Île-de-France à droite.
   Icônes : pictogrammes OFFICIELS Météo-France (PNG O/R) posés au centre des
   départements colorés (sauf Paris), niveaux forts => R, sinon => O.
   Pour les aléas sans picto officiel (grêle, verglas, brouillard, feu,
   littoral), pictogramme vectoriel transparent avec halo.
   ========================================================================== */
(function () {
    'use strict';

    var LOGO_CANDIDATES = ['assets/logo.png', 'vigilance-assets/logo.png', 'logo.png'];
    var PICTO_BASES = ['assets/mf-vigiciel/', 'vigilance-assets/mf-vigiciel/'];
    // Série vigiciel (silhouettes Météo-France) — 9 aléas sur 11.
    var PICTO_SVG = {
        vent: 'Vent.svg', pluie_inondation: 'Pluie.svg', orages: 'Orages.svg',
        neige: 'Neige.svg', verglas: 'Pluie verglaçante.svg', chaleur: 'Canicule.svg',
        froid: 'froid.svg', brouillard: 'Brouillard-givrant.svg', littoral: 'vague.svg',
        feu: 'Feu.svg'
    };
    var IDF_SKIP = ['75', '77', '78', '91', '92', '93', '94', '95'];

    var W = 2200;
    var H = 1640;
    var MARGIN = 24;
    var BANNER_Y = 24;
    var BANNER_H = 175;
    var FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    var pictoCache = {};

    function ready(fn) { if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

    function loadImage(urls, index, done) {
        index = index || 0;
        if (index >= urls.length) { done(null); return; }
        var img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = function () { done(img); };
        img.onerror = function () { loadImage(urls, index + 1, done); };
        img.src = urls[index];
    }

    function loadPicto(hazard) {
        if (pictoCache[hazard]) return pictoCache[hazard];
        var name = PICTO_SVG[hazard];
        var urls = PICTO_BASES.map(function (b) { return b + encodeURIComponent(name); });
        pictoCache[hazard] = new Promise(function (resolve) {
            (function tryFetch(i) {
                if (i >= urls.length) { resolve(null); return; }
                fetch(urls[i], { cache: 'force-cache' }).then(function (r) {
                    if (!r.ok) throw new Error('http ' + r.status);
                    return r.text();
                }).then(function (svgText) {
                    // Silhouette noire -> blanche (transparent), comme sur la carte MF
                    var white = svgText.replace(/#000000/gi, '#ffffff');
                    var blob = new Blob([white], { type: 'image/svg+xml;charset=utf-8' });
                    var img = new Image();
                    img.onload = function () { resolve(img); };
                    img.onerror = function () { resolve(null); };
                    img.src = URL.createObjectURL(blob);
                }).catch(function () { tryFetch(i + 1); });
            })(0);
        });
        return pictoCache[hazard];
    }

    function node(selector) {
        return document.querySelector('.hrw-card ' + selector) || document.querySelector(selector);
    }

    function activeTabText(root, selector) {
        var el = root.querySelector(selector + ' .hrw-tab.is-active');
        return el ? (el.textContent || '').trim() : '';
    }

    function roundRectPath(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }

    function exportFilename(hazard, day) {
        var safe = function (s) { return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'carte'; };
        return 'vigilance-' + safe(hazard) + '-' + safe(day) + '.png';
    }

    function rgbKey(color) {
        if (!color) return '';
        color = String(color).trim();
        var m = color.match(/^#([0-9a-f]{6})$/i);
        if (m) {
            var n = parseInt(m[1], 16);
            return (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255);
        }
        m = color.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
        if (m) return m[1] + ',' + m[2] + ',' + m[3];
        return '';
    }

    function serializeSvg(svg, removeAllIcons) {
        var clone = svg.cloneNode(true);
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
        // Inlinise les styles calculés (sinon : ronds noirs à l'export).
        (function inlineStyles(orig) {
            var walk = function (a, b) {
                if (a && b && a.nodeType === 1) {
                    var s = window.getComputedStyle(a);
                    var cp = function (prop, attr) { var v = s.getPropertyValue(prop); if (v && v !== '' && v !== 'none') b.setAttribute(attr, v); };
                    cp('fill', 'fill'); cp('fill-opacity', 'fill-opacity'); cp('stroke', 'stroke');
                    cp('stroke-width', 'stroke-width'); cp('stroke-opacity', 'stroke-opacity'); cp('opacity', 'opacity');
                    if (s.getPropertyValue('display') === 'none') b.setAttribute('display', 'none');
                }
                var ac = a ? a.children : [], bc = b ? b.children : [];
                for (var i = 0; i < bc.length; i++) walk(ac[i], bc[i]);
            };
            walk(orig, clone);
        })(svg);

        if (removeAllIcons) {
            clone.querySelectorAll('g.hrw-dept-icon-wrap').forEach(function (g) { g.remove(); });
        } else {
            // Pictogrammes vectoriels « transparents » (aléas sans PNG officiel)
            clone.querySelectorAll('circle.hrw-dept-icon-badge').forEach(function (c) { c.remove(); });
            clone.querySelectorAll('g.hrw-dept-icon').forEach(function (g) {
                var t = g.getAttribute('transform') || '';
                var m = t.match(/translate\(([\d.+-]+),([\d.+-]+)\) scale\(([\d.]+)\)/);
                if (m) g.setAttribute('transform', 'translate(' + m[1] + ',' + m[2] + ') scale(' + (parseFloat(m[3]) * 2.6).toFixed(3) + ')');
            });
            clone.querySelectorAll('g.hrw-dept-icon path, g.hrw-dept-icon circle, g.hrw-dept-icon rect').forEach(function (p) {
                p.setAttribute('stroke', 'rgba(255,255,255,0.92)');
                p.setAttribute('stroke-width', '2.6');
                p.setAttribute('paint-order', 'stroke');
                p.setAttribute('stroke-linejoin', 'round');
            });
        }
        clone.querySelectorAll('path').forEach(function (p) {
            if (!p.getAttribute('fill')) p.setAttribute('fill', '#31aa35');
            if (p.getAttribute('data-code')) {
                p.setAttribute('stroke', '#05080c');
                p.setAttribute('stroke-width', '2.4');
                p.setAttribute('stroke-linejoin', 'round');
            }
        });
        return new XMLSerializer().serializeToString(clone);
    }

    function drawSvgImage(ctx, svg, x, y, size, removeAllIcons) {
        return new Promise(function (resolve) {
            var blob = new Blob([serializeSvg(svg, removeAllIcons)], { type: 'image/svg+xml;charset=utf-8' });
            var url = URL.createObjectURL(blob);
            var img = new Image();
            img.onload = function () { ctx.drawImage(img, x, y, size, size); URL.revokeObjectURL(url); resolve(); };
            img.onerror = function () { URL.revokeObjectURL(url); resolve(); };
            img.src = url;
        });
    }

    function renderExport(card, callback) {
        var svg = node('[data-hrw-map]');
        var insetSvg = node('[data-hrw-inset-map]');
        if (!svg) { callback(new Error('Carte non trouvée')); return; }

        var hazard = activeTabText(card, '.hrw-hazard-tabs') || 'Vigilance';
        var day = activeTabText(card, '.hrw-day-tabs') || '';
        // CLÉ technique de l'aléa (dataset.hazard : 'orages', 'pluie_inondation'…)
        // — la lecture du libellé seul empêchait la reconnaissance des pictos.
        var hazardBtn = card.querySelector('.hrw-hazard-tabs .hrw-tab.is-active');
        var hazardKey = hazardBtn ? String(hazardBtn.getAttribute('data-hazard') || '').toLowerCase() : '';
        if (!hazardKey && hazard) {
            var labelToKey = { 'vent': 'vent', 'pluie-inondation': 'pluie_inondation', 'orages': 'orages', 'grêle': 'grele', 'chaleur': 'chaleur', 'froid': 'froid', 'neige': 'neige', 'verglas': 'verglas', 'brouillard': 'brouillard', 'littoral': 'littoral', 'feu': 'feu' };
            hazardKey = labelToKey[hazard.toLowerCase()] || '';
        }
        var hasOfficial = Object.prototype.hasOwnProperty.call(PICTO_SVG, hazardKey);
        var legendTitle = ((card.querySelector('[data-hrw-legend-title]') || {}).textContent || hazard).trim();

        var items = Array.prototype.map.call(
            card.querySelectorAll('.hrw-legend .hrw-legend-item'),
            function (el) {
                var swatch = el.querySelector('.hrw-legend-swatch');
                return { color: (swatch && swatch.style.backgroundColor) || '#31aa35', label: (el.textContent || '').trim() };
            }
        );
        if (!items.length) items = [{ color: '#31aa35', label: 'Nul' }];
        var maxIdx = items.length - 1;
        var levelByColor = {};
        items.forEach(function (it, idx) { levelByColor[rgbKey(it.color)] = idx; });

        var hasOfficialKey = hasOfficial;
        var vb = svg.viewBox.baseVal || { width: 1000, height: 1000 };

        loadImage(LOGO_CANDIDATES, 0, function (logo) {
            var canvas = document.createElement('canvas');
            canvas.width = W;
            canvas.height = H;
            var ctx = canvas.getContext('2d');
            ctx.fillStyle = '#0b1220';
            ctx.fillRect(0, 0, W, H);

            var mapSize = H - 20;
            var mapX = (W - mapSize) / 2;

            drawSvgImage(ctx, svg, Math.round(mapX), 10, mapSize, true).then(function () {
                // Pictogrammes officiels sur les départements colorés (hors Paris / IDF)
                var pictos = [];
                if (hasOfficial) {
                    Array.prototype.forEach.call(svg.querySelectorAll('path[data-code]'), function (path) {
                        var code = path.getAttribute('data-code');
                        if (!code || code === '75' || IDF_SKIP.indexOf(code) !== -1) return;
                        var level = levelByColor[rgbKey(path.getAttribute('fill'))];
                        if (level === undefined || level <= 0) return;
                        var bb = path.getBBox();
                        if (!bb || !bb.width) return;
                        var cxp = mapX + ((bb.x + bb.width / 2) / (vb.width || 1000)) * mapSize;
                        var cyp = 10 + ((bb.y + bb.height / 2) / (vb.height || 1000)) * mapSize;
                        pictos.push({ x: cxp, y: cyp });
                    });
                }
                var iconSize = Math.round(mapSize * 0.024);
                loadPicto(hazard).then(function (hazardImg) {
                    // Encart Île-de-France
                    if (insetSvg) {
                        var panelW = 470, panelH = 560, px = W - MARGIN - panelW, py = 400;
                        ctx.fillStyle = 'rgba(7, 11, 20, 0.95)';
                        roundRectPath(ctx, px, py, panelW, panelH, 18); ctx.fill();
                        ctx.strokeStyle = 'rgba(0, 210, 255, 0.6)'; ctx.lineWidth = 2.5; ctx.stroke();
                        ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
                        ctx.fillStyle = '#9fdcff'; ctx.font = '800 34px ' + FONT;
                        ctx.fillText('Île-de-France', px + panelW / 2, py + 52);
                        ctx.fillStyle = '#93a5bf'; ctx.font = '500 24px ' + FONT;
                        ctx.fillText('zoom — ' + hazard + (day ? ' · ' + day : ''), px + panelW / 2, py + 88);
                        ctx.textAlign = 'left';
                        drawSvgImage(ctx, insetSvg, px + 18, py + 110, panelW - 36, !hasOfficial);
                    }

                    // Logo haut droite
                    var logoTargetW = 150, lx = W - MARGIN - logoTargetW, ly = BANNER_Y + (BANNER_H - logoTargetW) / 2;
                    ctx.save();
                    ctx.shadowColor = 'rgba(0, 0, 0, 0.75)'; ctx.shadowBlur = 12; ctx.shadowOffsetX = 2; ctx.shadowOffsetY = 2;
                    if (logo) { ctx.drawImage(logo, lx, ly, logoTargetW, logoTargetW); }
                    else {
                        ctx.textAlign = 'right'; ctx.textBaseline = 'top';
                        ctx.font = '800 38px ' + FONT; ctx.fillStyle = '#ffffff';
                        ctx.fillText('MÉTÉO-CLIMAT', W - MARGIN, BANNER_Y + 20);
                        ctx.font = '900 32px ' + FONT; ctx.fillStyle = '#00d2ff';
                        ctx.fillText('PRO', W - MARGIN, BANNER_Y + 68);
                        ctx.textAlign = 'left';
                    }
                    ctx.restore();

                    // Cartouche antenne haut gauche
                    var paramTitle = hazard;
                    var modelAndRun = 'AROME HD (Météo-France) — vigilance non officielle';
                    var dateText = day;
                    ctx.font = '700 38px ' + FONT; var w1 = ctx.measureText(paramTitle).width;
                    ctx.font = '700 26px ' + FONT; var w2 = ctx.measureText(modelAndRun).width;
                    ctx.font = '800 34px ' + FONT; var w3 = ctx.measureText(dateText).width;
                    var bannerW = Math.max(w1, w2, w3) + 48;
                    ctx.fillStyle = 'rgba(7, 11, 20, 0.94)';
                    roundRectPath(ctx, MARGIN, BANNER_Y, bannerW, BANNER_H, 16); ctx.fill();
                    ctx.strokeStyle = 'rgba(0, 210, 255, 0.8)'; ctx.lineWidth = 3; ctx.stroke();
                    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
                    ctx.fillStyle = '#ffffff'; ctx.font = '700 38px ' + FONT;
                    ctx.fillText(paramTitle, MARGIN + 24, BANNER_Y + 48);
                    ctx.fillStyle = '#00d2ff'; ctx.font = '700 26px ' + FONT;
                    ctx.fillText(modelAndRun, MARGIN + 24, BANNER_Y + 88);
                    ctx.fillStyle = '#ffffff'; ctx.font = '800 34px ' + FONT;
                    ctx.fillText(dateText, MARGIN + 24, BANNER_Y + 140);

                    // Légende basse centrée
                    var legendW = 1180, legendH = 132, legendBottom = 18;
                    var legendX = (W - legendW) / 2, legendY = H - legendH - legendBottom;
                    ctx.fillStyle = 'rgba(7, 11, 20, 0.96)';
                    roundRectPath(ctx, legendX - 22, legendY - 18, legendW + 44, legendH + 50, 18); ctx.fill();
                    ctx.strokeStyle = 'rgba(0, 210, 255, 0.7)'; ctx.lineWidth = 2.5; ctx.stroke();
                    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
                    ctx.fillStyle = '#ffffff'; ctx.font = '700 30px ' + FONT;
                    ctx.fillText('Légende — ' + legendTitle, W / 2, legendY + 30);
                    var barY = legendY + 50, segW = legendW / items.length, segX = legendX;
                    items.forEach(function (it) {
                        ctx.fillStyle = it.color; ctx.fillRect(segX, barY, segW - 2, 28); segX += segW;
                    });
                    var labelFont = items.length > 7 ? 17 : 20;
                    ctx.fillStyle = '#c7d3e4'; ctx.font = '600 ' + labelFont + 'px ' + FONT;
                    items.forEach(function (it, idx) {
                        var cx = legendX + segW * (idx + 0.5), text = it.label;
                        if (ctx.measureText(text).width > segW - 8) {
                            while (ctx.measureText(text + '…').width > segW - 8 && text.length > 2) text = text.slice(0, -1);
                            text += '…';
                        }
                        ctx.textAlign = 'center';
                        ctx.fillText(text, cx, barY + 64);
                    });
                    ctx.textAlign = 'left';

                    // Pictogrammes officiels Météo-France (série vigiciel) sur les départements colorés
                    pictos.forEach(function (p) {
                        if (!hazardImg) return;
                        var s = iconSize;
                        ctx.save();
                        ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 6;
                        ctx.drawImage(hazardImg, p.x - s / 2, p.y - s / 2, s, s);
                        ctx.restore();
                    });

                    canvas.toBlob(function (blob) {
                        if (!blob) { callback(new Error('Export impossible')); return; }
                        var url = URL.createObjectURL(blob);
                        var a = document.createElement('a');
                        a.href = url;
                        a.download = exportFilename(hazard, day);
                        document.body.appendChild(a);
                        a.click();
                        setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1200);
                        callback(null, blob);
                    }, 'image/png');
                });
            });
        });
    }

    function injectButton(card) {
        var tools = card.querySelector('.hrw-map-tools');
        if (!tools || tools.querySelector('[data-hrw-export-cartouche]')) return;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('data-hrw-export-cartouche', '1');
        btn.title = 'Télécharger la carte 2200×1640 avec pictos officiels Météo-France';
        btn.textContent = '⬇️ Télécharger (pictos Météo-France)';
        btn.style.cssText = 'background:linear-gradient(135deg,rgba(0,210,255,.25),rgba(2,132,199,.22));' +
            'border:1px solid rgba(0,210,255,.55);color:#fff;border-radius:9px;padding:6px 10px;font-weight:800;font-size:12px;cursor:pointer;';
        btn.addEventListener('click', function () {
            btn.disabled = true;
            var old = btn.textContent;
            btn.textContent = 'Génération 2200×1640…';
            renderExport(card, function (err) {
                btn.disabled = false;
                btn.textContent = old;
                if (err) window.alert('Export : ' + err.message);
            });
        });
        tools.appendChild(btn);
    }

    ready(function () {
        var timer = setInterval(function () {
            var card = document.querySelector('.hrw-card[data-hrw-app]');
            if (!card) { clearInterval(timer); return; }
            if (card.querySelector('.hrw-legend-item')) { injectButton(card); clearInterval(timer); }
        }, 800);
        // Diagnostic / test automatique : /...?auto=1 déclenche un export
        // quelques secondes après le chargement et expose le résultat.
        if (/[?&]auto=1/.test(location.search)) {
            setTimeout(function () {
                var btn = document.querySelector('[data-hrw-export-cartouche]');
                if (!btn) { document.title = 'EXPORT_ERR:no_button'; return; }
                document.title = 'EXPORT_START';
                var done = false;
                var finish = function (err) {
                    if (done) return;
                    done = true;
                    document.title = err ? ('EXPORT_ERR:' + err.message) : 'EXPORT_OK';
                };
                try {
                    renderExport(document.querySelector('.hrw-card'), finish);
                } catch (e) { finish(e); }
            }, 6000);
            setTimeout(function () { if (document.title === 'EXPORT_START') document.title = 'EXPORT_PENDING'; }, 25000);
        }
    });
})();
