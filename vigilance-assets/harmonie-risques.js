(function () {
    'use strict';

    var COMMUNES_API = 'https://geo.api.gouv.fr/communes';
    var SVG_NS = 'http://www.w3.org/2000/svg';
    var IDF_CODES = ['75', '77', '78', '91', '92', '93', '94', '95'];
    // Départements côtiers — même liste que LITTORAL_DEPARTMENTS côté
    // pipeline Python (update_risques.py) : seuls ces départements peuvent
    // avoir un niveau Littoral non nul, donc seuls ceux-là reçoivent un
    // tracé sur le trait de côte.
    var LITTORAL_DEPARTMENT_CODES = [
        '59', '62', '80', '76', '14', '50', '35', '22', '29', '56',
        '44', '85', '17', '33', '40', '64',
        '66', '11', '34', '30', '13', '83', '06',
        '2A', '2B'
    ];
    var ICON_MIN_LEVEL = 1;

    // Icônes vectorielles épurées (monochromes, viewBox 24x24, dessinées à
    // la main — pas d'emoji, ni de dépendance externe). Chaque primitive
    // est rejouée à la fois en HTML (onglets, détail) et en SVG (badges sur
    // la carte) à partir de la même définition, pour éviter toute
    // divergence visuelle entre les deux usages.
    var ICONS = {
        orages: [
            { tag: 'path', d: 'M13 2 3 14h6l-1 8 10-12h-6l1-8z', fill: 'currentColor' }
        ],
        grele: [
            { tag: 'circle', cx: 7, cy: 9, r: 2.6, fill: 'currentColor' },
            { tag: 'circle', cx: 15, cy: 7, r: 2.1, fill: 'currentColor' },
            { tag: 'circle', cx: 11.5, cy: 15.5, r: 3, fill: 'currentColor' }
        ],
        pluie_inondation: [
            { tag: 'circle', cx: 8, cy: 11, r: 3.4, fill: 'currentColor' },
            { tag: 'circle', cx: 13, cy: 8.5, r: 4.4, fill: 'currentColor' },
            { tag: 'circle', cx: 17.2, cy: 11, r: 3.4, fill: 'currentColor' },
            { tag: 'rect', x: 5.4, y: 11, width: 13.6, height: 5.2, rx: 2.6, fill: 'currentColor' },
            { tag: 'path', d: 'M8 19.5l1.2 3h-2.4z', fill: 'currentColor' },
            { tag: 'path', d: 'M13 19.5l1.2 3h-2.4z', fill: 'currentColor' },
            { tag: 'path', d: 'M18 19.5l1.2 3h-2.4z', fill: 'currentColor' }
        ],
        vent: [
            { tag: 'path', d: 'M3 8h10.5a3 3 0 1 0-2.6-4.6', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round', fill: 'none' },
            { tag: 'path', d: 'M3 13h14.5a3 3 0 1 1-2.6 4.6', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round', fill: 'none' },
            { tag: 'path', d: 'M3 18h9', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round', fill: 'none' }
        ],
        neige: [
            { tag: 'line', x1: 12, y1: 2, x2: 12, y2: 22, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 4.2, y1: 7, x2: 19.8, y2: 17, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 19.8, y1: 7, x2: 4.2, y2: 17, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }
        ],
        verglas: [
            { tag: 'ellipse', cx: 12, cy: 16.5, rx: 8, ry: 3.2, fill: 'currentColor', opacity: '.35' },
            { tag: 'line', x1: 7, y1: 15, x2: 10, y2: 11.5, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 12, y1: 14.5, x2: 15, y2: 9.5, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 16, y1: 15, x2: 19, y2: 10.5, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }
        ],
        chaleur: [
            { tag: 'circle', cx: 12, cy: 12, r: 4.2, fill: 'currentColor' },
            { tag: 'line', x1: 12, y1: 1.5, x2: 12, y2: 4.5, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 12, y1: 19.5, x2: 12, y2: 22.5, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 1.5, y1: 12, x2: 4.5, y2: 12, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 19.5, y1: 12, x2: 22.5, y2: 12, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 4.6, y1: 4.6, x2: 6.7, y2: 6.7, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 17.3, y1: 17.3, x2: 19.4, y2: 19.4, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 4.6, y1: 19.4, x2: 6.7, y2: 17.3, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 17.3, y1: 6.7, x2: 19.4, y2: 4.6, stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }
        ],
        froid: [
            { tag: 'path', d: 'M12 3a2 2 0 0 0-2 2v8.1a4.2 4.2 0 1 0 4 0V5a2 2 0 0 0-2-2z', stroke: 'currentColor', 'stroke-width': 1.8, fill: 'none' },
            { tag: 'circle', cx: 12, cy: 18, r: 2.4, fill: 'currentColor' }
        ],
        brouillard: [
            { tag: 'line', x1: 4, y1: 7, x2: 20, y2: 7, stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 2.5, y1: 12, x2: 21.5, y2: 12, stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round' },
            { tag: 'line', x1: 4, y1: 17, x2: 20, y2: 17, stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round' }
        ],
        littoral: [
            { tag: 'path', d: 'M2 8c2 0 2-2.2 4-2.2s2 2.2 4 2.2 2-2.2 4-2.2 2 2.2 4 2.2 2-2.2 4-2.2', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', fill: 'none' },
            { tag: 'path', d: 'M2 13.5c2 0 2-2.2 4-2.2s2 2.2 4 2.2 2-2.2 4-2.2 2 2.2 4 2.2 2-2.2 4-2.2', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', fill: 'none' },
            { tag: 'path', d: 'M2 19c2 0 2-2.2 4-2.2s2 2.2 4 2.2 2-2.2 4-2.2 2 2.2 4 2.2 2-2.2 4-2.2', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', fill: 'none' }
        ],
        feu: [
            { tag: 'path', d: 'M12 2c1.6 2.8 1 4.6-.3 6.4-1.1 1.5-2.4 3-2.4 5.3a3.7 3.7 0 0 0 7.4 0c0-1.4-.5-2.3-1-3.1.2 1.2-.4 2-.4 2 .5-2.6-.9-4.4-1.7-5.6.2 1-.3 1.6-.3 1.6.4-2.6-.6-4.4-1.3-6.6z', fill: 'currentColor' },
            { tag: 'path', d: 'M11.2 22c-2.6 0-4.6-1.8-4.6-4.3 0-1.6.8-2.8 1.6-3.7-.2 1.3.3 2.1.3 2.1-.3-1.8.7-3 1.5-3.8-.1 1 .2 1.6.2 1.6 0-1.6 1-2.6 1-2.6-.6 1.8.2 3 .2 3 .7.4 1.2 1.2 1.2 2.2 0 1.6-1 2.5-1.4 3.5.6-.2 1.1-.6 1.4-1.1-.1 1.8-1.5 3.1-3.4 3.1z', fill: 'currentColor', opacity: '.55' }
        ]
    };

    function createSvgElement(tag, attrs) {
        var node = document.createElementNS(SVG_NS, tag);
        Object.keys(attrs || {}).forEach(function (key) {
            node.setAttribute(key, attrs[key]);
        });
        return node;
    }

    function appendIconPrimitives(container, name) {
        (ICONS[name] || []).forEach(function (primitive) {
            var attrs = {};
            Object.keys(primitive).forEach(function (key) {
                if (key !== 'tag') { attrs[key] = primitive[key]; }
            });
            container.appendChild(createSvgElement(primitive.tag, attrs));
        });
    }

    function buildIconNode(name, className) {
        var svg = createSvgElement('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true', focusable: 'false' });
        svg.setAttribute('class', className);
        appendIconPrimitives(svg, name);
        return svg;
    }

    // 3 paliers par aléa (léger / modéré / sévère), choisis en fonction de
    // la position du niveau réel dans l'échelle de l'aléa (cf.
    // adviceTierIndex) — rien n'est affiché au niveau 0 (Nul).
    var ADVICE_TIERS = {
        orages: [
            'Des orages sont possibles. Consultez régulièrement les prévisions et restez attentifs.',
            'Des orages marqués sont attendus, avec un risque de grêle ou de rafales. Mettez à l’abri les objets sensibles.',
            'De violents orages sont attendus. Évitez les déplacements, éloignez-vous des points hauts et des zones exposées à la foudre.'
        ],
        grele: [
            'De la grêle est possible en cas d’averse orageuse.',
            'De la grêle marquée est possible. Mettez les véhicules à l’abri si possible.',
            'De la grêle intense est possible, avec un risque de dégâts. Mettez impérativement les véhicules et objets fragiles à l’abri.'
        ],
        pluie_inondation: [
            'De la pluie est attendue, pouvant localement provoquer des ruissellements.',
            'De fortes pluies sont attendues, avec un risque de ruissellement ou de débordement localisé. Évitez les sous-sols et les points bas.',
            'De très fortes pluies sont attendues, avec un risque d’inondation important. Ne vous engagez pas sur une route inondée et suivez les consignes des autorités.'
        ],
        vent: [
            'Des rafales de vent sont possibles. Rangez les objets légers susceptibles de s’envoler.',
            'De fortes rafales de vent sont attendues. Évitez les activités exposées et fixez ce qui peut être emporté.',
            'De violentes rafales de vent sont attendues. Évitez les déplacements non indispensables et restez à l’écart des arbres et structures fragiles.'
        ],
        neige: [
            'De la neige est possible, pouvant rendre les routes glissantes.',
            'Des chutes de neige marquées sont attendues. Anticipez vos déplacements et équipez votre véhicule si besoin.',
            'De fortes chutes de neige sont attendues. Évitez les déplacements non indispensables et suivez l’évolution des conditions de circulation.'
        ],
        verglas: [
            'Un risque de verglas localisé est possible au sol.',
            'Un risque de pluie verglaçante est possible : la chaussée peut devenir brutalement glissante. Adaptez votre conduite.',
            'Un épisode durable de pluie verglaçante est attendu. Évitez les déplacements non indispensables, la chaussée peut rester dangereuse plusieurs heures.'
        ],
        chaleur: [
            'Des températures élevées sont attendues. Hydratez-vous régulièrement.',
            'De fortes chaleurs sont attendues. Évitez les efforts aux heures les plus chaudes et surveillez les personnes fragiles.',
            'Une chaleur extrême est attendue. Limitez les sorties et les efforts, hydratez-vous fréquemment, veillez sur les personnes vulnérables.'
        ],
        froid: [
            'Des températures basses sont attendues. Pensez à vous couvrir.',
            'Un froid marqué est attendu. Limitez les expositions prolongées et protégez les canalisations sensibles au gel.',
            'Un froid extrême est attendu. Évitez les expositions prolongées et soyez vigilant vis-à-vis des personnes vulnérables et des risques de gel.'
        ],
        brouillard: [
            'La visibilité peut être réduite par endroits.',
            'La visibilité peut être fortement réduite. Réduisez votre vitesse et augmentez les distances de sécurité.',
            'La visibilité peut être très fortement réduite (brouillard dense). Redoublez de prudence, envisagez de reporter vos déplacements.'
        ],
        feu: [
            'Les conditions météo peuvent légèrement favoriser le développement d’un feu. Respectez les consignes locales.',
            'Les conditions météo peuvent favoriser le développement d’un feu. Respectez les consignes locales et évitez tout départ de flamme.',
            'Les conditions météo sont très favorables au développement et à la propagation d’un feu. Soyez extrêmement vigilant et respectez strictement les interdictions locales.'
        ],
        littoral: [
            'Des rafales et une mer agitée sont possibles sur le littoral. Restez prudent en bord de mer.',
            'De fortes rafales accompagnées d’une dépression marquée sont attendues sur le littoral, avec un risque de mer forte à très forte. Éloignez-vous du bord de mer et des ouvrages exposés.',
            'De violentes rafales et une tempête marquée sont attendues sur le littoral, avec un risque de submersion. Évitez tout déplacement en bord de mer et suivez les consignes des autorités.'
        ]
    };
    var FEU_DISCLAIMER = 'Important : ce niveau mesure seulement le cocktail météo chaleur, humidité, vent et pluie. Il reste non officiel et ne remplace pas la Météo des forêts.';
    var LITTORAL_DISCLAIMER = 'Important : ce niveau mesure seulement les rafales et la pression (pas de données de vagues, marée ni surcote). Il reste non officiel et ne remplace pas la Vigilance vagues-submersion de Météo-France.';

    function whenReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
        } else {
            callback();
        }
    }

    function fetchJson(url, options) {
        return fetch(url, Object.assign({ cache: 'no-cache' }, options || {})).then(function (response) {
            if (!response.ok) {
                throw new Error('Réponse HTTP ' + response.status);
            }
            return response.json();
        });
    }

    function fetchText(url) {
        return fetch(url, { cache: 'default' }).then(function (response) {
            if (!response.ok) {
                throw new Error('Réponse HTTP ' + response.status);
            }
            return response.text();
        });
    }

    // Certains thèmes (Avada/Fusion Builder) placent le shortcode dans une
    // colonne bien plus étroite que la ligne qui la contient. On mesure les
    // ancêtres réels au lieu de deviner une largeur fixe (même pattern que
    // harmonie-knmi.js, déjà corrigé d'une boucle infinie rétréci/agrandi).
    function clearWiden(card) {
        card.style.width = '';
        card.style.maxWidth = '';
        card.style.marginLeft = '';
        card.style.marginRight = '';
    }

    function widenToFitAncestor(card) {
        if (!card) {
            return;
        }
        if (window.innerWidth < 900) {
            clearWiden(card);
            return;
        }
        var parent = card.parentElement;
        if (!parent) {
            return;
        }
        clearWiden(card);
        var parentWidth = parent.getBoundingClientRect().width;
        var widest = parentWidth;
        var el = parent.parentElement;
        var hops = 0;
        while (el && hops < 6) {
            var rect = el.getBoundingClientRect();
            if (rect.width > widest) {
                widest = rect.width;
            }
            el = el.parentElement;
            hops += 1;
        }
        var viewportLimit = (document.documentElement.clientWidth || window.innerWidth) - 4;
        var target = Math.min(widest, 1700, viewportLimit);
        if (target <= parentWidth + 24) {
            return;
        }
        var offset = (target - parentWidth) / 2;
        card.style.maxWidth = target + 'px';
        card.style.width = target + 'px';
        card.style.marginLeft = (-offset) + 'px';
        card.style.marginRight = (-offset) + 'px';
    }

    // --- Projection GeoJSON -> SVG (équirectangulaire, corrigée en cosinus
    // de latitude pour ne pas déformer la France) : même principe que la
    // projection du fond de carte HARMONIE, mais bornes calculées
    // dynamiquement depuis les contours eux-mêmes plutôt que codées en dur.
    function computeBoundsFromFeatures(features) {
        var west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
        function visit(coords, depth) {
            if (depth === 0) {
                var lon = coords[0], lat = coords[1];
                if (lon < west) { west = lon; }
                if (lon > east) { east = lon; }
                if (lat < south) { south = lat; }
                if (lat > north) { north = lat; }
            } else {
                coords.forEach(function (item) { visit(item, depth - 1); });
            }
        }
        features.forEach(function (feature) {
            var geometry = feature.geometry;
            if (!geometry) { return; }
            var depth = geometry.type === 'Polygon' ? 2 : 3;
            visit(geometry.coordinates, depth);
        });
        return { west: west, east: east, south: south, north: north };
    }

    function buildProjector(bounds, viewSize, padding) {
        var latMid = (bounds.south + bounds.north) / 2;
        var scaleFactor = Math.cos(latMid * Math.PI / 180);
        var spanX = (bounds.east - bounds.west) * scaleFactor;
        var spanY = bounds.north - bounds.south;
        var usable = viewSize - padding * 2;
        var scale = usable / Math.max(spanX, spanY);
        var offsetX = padding + (usable - spanX * scale) / 2;
        var offsetY = padding + (usable - spanY * scale) / 2;
        return function project(lon, lat) {
            var x = (lon - bounds.west) * scaleFactor * scale + offsetX;
            var y = (bounds.north - lat) * scale + offsetY;
            return [x, y];
        };
    }

    function projectRing(ring, project) {
        return ring.map(function (point) { return project(point[0], point[1]); });
    }

    function pathForGeometry(geometry, project) {
        var polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
        var parts = [];
        polygons.forEach(function (polygon) {
            polygon.forEach(function (ring) {
                var points = projectRing(ring, project);
                var d = '';
                points.forEach(function (xy, index) {
                    d += (index === 0 ? 'M' : 'L') + xy[0].toFixed(2) + ',' + xy[1].toFixed(2) + ' ';
                });
                d += 'Z ';
                parts.push(d);
            });
        });
        return parts.join('');
    }

    // Centroïde (aire pondérée, formule du lacet) du plus grand contour
    // extérieur de la géométrie : plus fiable qu'une simple moyenne de
    // sommets pour placer une icône au centre visuel du département,
    // y compris pour les formes concaves ou multi-parties.
    function polygonSignedArea(points) {
        var sum = 0;
        for (var i = 0; i < points.length; i++) {
            var a = points[i];
            var b = points[(i + 1) % points.length];
            sum += a[0] * b[1] - b[0] * a[1];
        }
        return sum / 2;
    }

    function polygonCentroid(points) {
        var area = polygonSignedArea(points);
        if (Math.abs(area) < 1e-9) {
            var sx = 0, sy = 0;
            points.forEach(function (p) { sx += p[0]; sy += p[1]; });
            return [sx / points.length, sy / points.length];
        }
        var cx = 0, cy = 0;
        for (var i = 0; i < points.length; i++) {
            var a = points[i];
            var b = points[(i + 1) % points.length];
            var cross = a[0] * b[1] - b[0] * a[1];
            cx += (a[0] + b[0]) * cross;
            cy += (a[1] + b[1]) * cross;
        }
        return [cx / (6 * area), cy / (6 * area)];
    }

    function largestExteriorRingPoints(geometry, project) {
        var polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
        var best = null;
        var bestArea = -1;
        polygons.forEach(function (polygon) {
            if (!polygon.length) { return; }
            var points = projectRing(polygon[0], project);
            var area = Math.abs(polygonSignedArea(points));
            if (area > bestArea) {
                bestArea = area;
                best = points;
            }
        });
        return best || [];
    }

    // --- Trait littoral : le tracé Natural Earth (littoral-coastline.geojson,
    // même source que les cartes raster HARMONIE/AROME) est indépendant du
    // GeoJSON départemental — pas de correspondance directe entre ses points
    // et un département. On rattache chaque point du trait de côte au
    // département dont un sommet du contour est le plus proche (les deux
    // tracés suivent la même côte réelle, donc restent proches l'un de
    // l'autre), puis on découpe le trait en tronçons consécutifs de même
    // département pour pouvoir colorer chaque tronçon selon son niveau
    // d'alerte Littoral.
    function departmentExteriorLonLat(geometry) {
        var polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
        var points = [];
        polygons.forEach(function (polygon) {
            if (polygon.length) { points = points.concat(polygon[0]); }
        });
        return points;
    }

    function pointToSegmentDistanceSquared(px, py, ax, ay, bx, by) {
        var dx = bx - ax;
        var dy = by - ay;
        var lengthSquared = dx * dx + dy * dy;
        var t = lengthSquared > 0 ? ((px - ax) * dx + (py - ay) * dy) / lengthSquared : 0;
        t = Math.max(0, Math.min(1, t));
        var cx = ax + t * dx;
        var cy = ay + t * dy;
        var ex = px - cx;
        var ey = py - cy;
        return ex * ex + ey * ey;
    }

    function buildLittoralRuns(deptFeatures, coastGeojson, project) {
        var deptPoints = {};
        deptFeatures.forEach(function (feature) {
            var code = String((feature.properties || {}).code || '').toUpperCase();
            if (LITTORAL_DEPARTMENT_CODES.indexOf(code) === -1 || !feature.geometry) { return; }
            deptPoints[code] = departmentExteriorLonLat(feature.geometry);
        });
        var codes = Object.keys(deptPoints);
        if (!codes.length) { return []; }

        // Distance au contour (segment par segment), pas au sommet le plus
        // proche : un contour départemental n'a que quelques sommets le
        // long d'un tronçon de côte à peu près droit, donc la distance au
        // sommet le plus proche pouvait rester grande même pour un point du
        // trait de côte réellement à l'intérieur de ce département.
        //
        // Toujours renvoyer le département le plus proche, sans seuil de
        // rejet : un seuil laissait des trous visibles dans le trait à
        // chaque endroit où le tracé Natural Earth s'écarte un peu plus du
        // contour IGN (estuaires, caps), y compris entre deux départements
        // pourtant tous deux en alerte — exactement le défaut signalé
        // (couleurs qui ne se rejoignent pas). Le seul cas où ce choix
        // « au plus proche, toujours » déborde un peu est la portion de
        // côte belge/espagnole/italienne dans la marge de la zone
        // d'extraction, rattachée par défaut au département français
        // voisin le plus proche (Nord/Pyrénées-Orientales/Alpes-Maritimes)
        // — un léger débordement plutôt qu'un vide, plus proche de ce qui
        // était demandé.
        // Le trait Natural Earth suit la côte physique, pas les frontières
        // politiques : sans coupure, la côte belge (au nord du Nord),
        // espagnole (au sud des Pyrénées-Orientales) et italienne (à l'est
        // des Alpes-Maritimes) se rattachaient au département français le
        // plus proche et débordaient hors de France. Coordonnées
        // approximatives des points frontière réels sur la côte (De Panne,
        // Cerbère, Menton) — au-delà, on ignore le point plutôt que de
        // prolonger le trait sur un pays voisin.
        var BORDER_CUTOFFS = {
            '59': function (lon, lat) { return lat > 51.10; },
            '66': function (lon, lat) { return lat < 42.40; },
            '06': function (lon, lat) { return lon > 7.56; }
        };

        function nearestDepartmentInfo(lon, lat) {
            var bestCode = null;
            var bestDist = Infinity;
            codes.forEach(function (code) {
                var points = deptPoints[code];
                for (var i = 0; i < points.length - 1; i++) {
                    var dist = pointToSegmentDistanceSquared(
                        lon, lat,
                        points[i][0], points[i][1],
                        points[i + 1][0], points[i + 1][1]
                    );
                    if (dist < bestDist) {
                        bestDist = dist;
                        bestCode = code;
                    }
                }
            });
            return { code: bestCode, dist: bestDist };
        }

        function nearestDepartment(lon, lat) {
            var code = nearestDepartmentInfo(lon, lat).code;
            var cutoff = BORDER_CUTOFFS[code];
            if (cutoff && cutoff(lon, lat)) { return null; }
            return code;
        }

        // Le tracé Natural Earth couvre aussi les côtes britanniques et
        // anglo-normandes (Kent, Cornouailles, Jersey, Guernesey...) comme
        // tronçons séparés du même fichier — sans filtre, un tronçon
        // entièrement étranger peut quand même se voir rattaché au
        // département français le plus proche point par point (la Manche
        // est étroite : Douvres n'est qu'à ~34 km de Calais), ce qui
        // prolongeait le trait jusqu'en Angleterre. On ne garde donc un
        // tronçon entier que si une bonne part de ses points colle
        // réellement à un contour départemental français (0,4 mesuré
        // empiriquement : sépare nettement les tronçons français, à ≥ 0,74,
        // des tronçons anglo-normands, à ≤ 0,33).
        var FEATURE_KEEP_FRACTION = 0.4;

        function isFrenchFeature(coords) {
            if (!coords.length) { return false; }
            var within = 0;
            coords.forEach(function (coord) {
                if (nearestDepartmentInfo(coord[0], coord[1]).dist <= 0.09) { within += 1; }
            });
            return within / coords.length >= FEATURE_KEEP_FRACTION;
        }

        var runs = [];
        (coastGeojson.features || []).forEach(function (feature) {
            var geometry = feature.geometry;
            if (!geometry || geometry.type !== 'LineString') { return; }
            var coords = geometry.coordinates;
            if (!isFrenchFeature(coords)) { return; }
            var pointCodes = coords.map(function (coord) { return nearestDepartment(coord[0], coord[1]); });
            var index = 0;
            while (index < coords.length) {
                var code = pointCodes[index];
                if (!code) { index += 1; continue; }
                var segment = [coords[index]];
                var next = index + 1;
                while (next < coords.length && pointCodes[next] === code) {
                    segment.push(coords[next]);
                    next += 1;
                }
                // Le point de transition est répété en fin de tronçon pour
                // que deux départements français voisins se rejoignent au
                // même pixel plutôt que de laisser un blanc à leur jointure
                // — sauf si ce point suivant est au-delà d'une frontière
                // internationale (code null), où le trait doit justement
                // s'arrêter net.
                if (next < coords.length && pointCodes[next]) {
                    segment.push(coords[next]);
                }
                if (segment.length >= 2) {
                    runs.push({ code: code, points: segment });
                }
                index = next;
            }
        });

        return runs.map(function (run) {
            return { code: run.code, points: run.points.map(function (c) { return project(c[0], c[1]); }) };
        });
    }

    function zonedDateKey(iso, tz) {
        // Journée « météo » : se termine à 6h du matin plutôt qu'à minuit,
        // J+1 reprend à 6h — les heures 0h-6h restent rattachées à la
        // journée précédente. Même décalage appliqué côté pipeline Python
        // (cf. _effective_date dans update_risques.py) pour que la frise
        // et le badge du jour restent cohérents entre eux.
        var shifted = new Date(new Date(iso).getTime() - 6 * 60 * 60 * 1000);
        return new Intl.DateTimeFormat('en-CA', {
            timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit'
        }).format(shifted);
    }

    // Notation météo « Xz JJ/MM » (ex. « 21z 27/08 ») pour le cycle du
    // modèle, en plus du format « JJ/MM HH:MM UTC » déjà affiché — calculée
    // à partir du même run_time publié, donc toujours à jour automatiquement.
    function zNotation(date) {
        var parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'UTC', hourCycle: 'h23',
            hour: '2-digit', day: '2-digit', month: '2-digit'
        }).formatToParts(date);
        var get = function (type) {
            var part = parts.filter(function (p) { return p.type === type; })[0];
            return part ? part.value : '';
        };
        return get('hour') + 'z ' + get('day') + '/' + get('month');
    }

    function initApp(app) {
        var baseUrl = (app.dataset.baseUrl || '').replace(/\/+$/, '');
        var geojsonUrl = app.dataset.geojsonUrl || '';
        var littoralUrl = app.dataset.littoralUrl || '';
        var defaultDepartment = (app.dataset.defaultDepartment || '').toUpperCase();
        var defaultHazard = app.dataset.defaultHazard || 'orages';
        var timezone = app.dataset.timezone || 'Europe/Paris';

        var input = app.querySelector('.hrw-city-input');
        var locateButton = app.querySelector('[data-hrw-locate]');
        var searchResults = app.querySelector('[data-hrw-search-results]');
        var runMeta = app.querySelector('[data-hrw-run]');
        var generated = app.querySelector('[data-hrw-generated]');
        var nationalSummaryBox = app.querySelector('[data-hrw-national-summary]');
        var summaryTitle = app.querySelector('[data-hrw-national-summary-title]');
        var summaryMax = app.querySelector('[data-hrw-summary-max]');
        var summaryMin = app.querySelector('[data-hrw-summary-min]');
        var summaryGust = app.querySelector('[data-hrw-summary-gust]');
        var summaryPrecip = app.querySelector('[data-hrw-summary-precip]');
        var hazardTabs = app.querySelector('[data-hrw-hazard-tabs]');
        var dayTabs = app.querySelector('[data-hrw-day-tabs]');
        var mapSvg = app.querySelector('[data-hrw-map]');
        var insetSvg = app.querySelector('[data-hrw-inset-map]');
        var mapWrap = app.querySelector('.hrw-map-wrap');
        var mapLoading = app.querySelector('[data-hrw-map-loading]');
        var legendTitle = app.querySelector('[data-hrw-legend-title]');
        var legend = app.querySelector('[data-hrw-legend]');
        var detailPlaceholder = app.querySelector('[data-hrw-detail-placeholder]');
        var detailContent = app.querySelector('[data-hrw-detail-content]');
        var detailTitle = app.querySelector('[data-hrw-detail-title]');
        var detailGrid = app.querySelector('[data-hrw-detail-grid]');
        var friseHazardLabel = app.querySelector('[data-hrw-frise-hazard]');
        var friseTrack = app.querySelector('[data-hrw-frise-track]');
        var friseLabels = app.querySelector('[data-hrw-frise-labels]');
        var adviceBox = app.querySelector('[data-hrw-advice]');
        var adviceText = app.querySelector('[data-hrw-advice-text]');
        var captureButton = app.querySelector('[data-hrw-capture]');
        var copyButton = app.querySelector('[data-hrw-copy]');

        var manifest = null;
        var mapEntries = {};
        var namesByCode = {};
        var littoralRuns = [];
        var littoralOverlayGroup = null;
        var currentHazard = defaultHazard;
        var currentDayIndex = 0;
        var selectedDepartment = defaultDepartment || null;
        var detailHazard = defaultHazard;
        var debounceTimer = null;
        var searchController = null;

        function dayFormatter() {
            return new Intl.DateTimeFormat('fr-FR', {
                weekday: 'short', day: '2-digit', month: '2-digit', timeZone: timezone
            });
        }

        function hourFormatter() {
            return new Intl.DateTimeFormat('fr-FR', {
                hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: timezone
            });
        }

        function localHourOf(date) {
            // formatToParts() plutôt que format() : certaines données ICU
            // ajoutent un suffixe d'unité (« 3 h ») au format heure-seule
            // en fr-FR, ce qui casse Number() sur la chaîne complète —
            // confirmé empiriquement (les ticks affichaient « NaNh »).
            // Lire directement la part de type "hour" évite ce piège quel
            // que soit le comportement local du moteur.
            var parts = new Intl.DateTimeFormat('en-GB', {
                hour: '2-digit', hourCycle: 'h23', timeZone: timezone
            }).formatToParts(date);
            var hourPart = parts.filter(function (part) { return part.type === 'hour'; })[0];
            return hourPart ? Number(hourPart.value) : 0;
        }

        // La journée météo change à 6h (cf. _effective_date côté pipeline
        // Python) — un onglet laissé ouvert à cheval sur cette limite doit
        // basculer tout seul sur la carte suivante plutôt que de rester
        // figé sur les données de la veille jusqu'à un rechargement manuel.
        // Un rechargement complet plutôt qu'un nouveau fetch en place :
        // beaucoup plus simple et sûr que de rejouer toute la séquence
        // d'initialisation (carte, onglets, etc.) une seconde fois sans
        // dupliquer d'écouteurs d'évènements.
        function scheduleNextDayBoundaryReload() {
            var parts = new Intl.DateTimeFormat('en-GB', {
                timeZone: timezone, hourCycle: 'h23',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            }).formatToParts(new Date());
            var get = function (type) {
                var part = parts.filter(function (p) { return p.type === type; })[0];
                return part ? Number(part.value) : 0;
            };
            var secondsSinceMidnight = get('hour') * 3600 + get('minute') * 60 + get('second');
            var boundarySeconds = 6 * 3600;
            var secondsUntilBoundary = boundarySeconds - secondsSinceMidnight;
            if (secondsUntilBoundary <= 0) {
                secondsUntilBoundary += 24 * 3600;
            }
            window.setTimeout(function () {
                window.location.reload();
            }, secondsUntilBoundary * 1000);
        }

        function levelInfo(hazard, level) {
            var scale = manifest && manifest.hazard_levels ? manifest.hazard_levels[hazard] : null;
            var info = scale ? scale[String(level)] : null;
            return info || { label: 'Inconnu', color: '#555', text_color: '#ffffff' };
        }

        function maxLevelFor(hazard) {
            var scale = manifest && manifest.hazard_levels ? manifest.hazard_levels[hazard] : null;
            return scale ? Object.keys(scale).length - 1 : 4;
        }

        // « (X/N) » à côté du libellé : les échelles n'ont plus toutes le
        // même nombre de paliers (4 à 8 selon l'aléa), utile pour situer un
        // niveau sans avoir la légende sous les yeux. Rien n'est affiché
        // pour le niveau 0 (Nul) : « Nul (0/7) » n'a pas de sens, il n'y a
        // pas d'alerte à situer sur l'échelle.
        function levelSuffix(hazard, level) {
            if (!level) { return ''; }
            return ' (' + level + '/' + maxLevelFor(hazard) + ')';
        }

        function hazardLabel(hazard) {
            return (manifest && manifest.hazards && manifest.hazards[hazard]) || hazard;
        }

        // Sépare « Modérée (≥ 28 °C) » en un mot principal + un seuil
        // entre parenthèses, pour les afficher sur deux lignes (mot en
        // gras, seuil plus petit en dessous) plutôt qu'à la suite sur une
        // seule ligne dans une case étroite — un seul long fragment de
        // texte y était illisible même sans le suffixe « (X/N) ».
        function splitHazardLabel(label) {
            var match = /^(.*?)\s(\([^)]*\))$/.exec(label);
            return match ? { main: match[1], sub: match[2] } : { main: label, sub: '' };
        }

        function departmentLevel(code, hazard, dayIndex) {
            var department = manifest && manifest.departments ? manifest.departments[code] : null;
            if (!department || !department.daily || !department.daily[dayIndex]) {
                return 0;
            }
            var hazards = department.daily[dayIndex].hazards || {};
            return hazards[hazard] || 0;
        }

        // Aplat neutre des départements sur l'onglet Littoral : l'alerte s'y
        // lit uniquement sur le trait de côte (cf. paintLittoralOverlay), pas
        // sur un remplissage département par département comme les autres
        // aléas — un aplat coloré partout (y compris les départements non
        // côtiers, toujours à « Nul ») donnait l'impression trompeuse que
        // l'aléa concernait la France entière plutôt que le seul littoral.
        var LITTORAL_NEUTRAL_FILL = '#dfe6ea';

        function paintMap() {
            var isLittoral = currentHazard === 'littoral';
            Object.keys(mapEntries).forEach(function (code) {
                var level = departmentLevel(code, currentHazard, currentDayIndex);
                var color = isLittoral ? LITTORAL_NEUTRAL_FILL : levelInfo(currentHazard, level).color;
                var showIconForLevel = !isLittoral && level >= ICON_MIN_LEVEL;
                mapEntries[code].forEach(function (entry) {
                    entry.path.setAttribute('fill', color);
                    entry.path.classList.toggle('is-selected', code === selectedDepartment);
                    if (showIconForLevel && entry.showIcon) {
                        entry.glyph.replaceChildren();
                        appendIconPrimitives(entry.glyph, currentHazard);
                        entry.iconGroup.style.display = '';
                    } else {
                        entry.iconGroup.style.display = 'none';
                    }
                });
            });
            paintLittoralOverlay();
            updateHazardTabBorders();
        }

        // Entoure chaque onglet d'aléa d'une bordure colorée dès qu'une
        // alerte existe quelque part en France ce jour-là (couleur du
        // niveau maximal national, cf. nationalMaxLevel) — repérer d'un
        // coup d'œil quels aléas sont actifs sans avoir à cliquer sur
        // chaque onglet un par un.
        function updateHazardTabBorders() {
            if (!hazardTabs) { return; }
            Array.prototype.forEach.call(hazardTabs.children, function (button) {
                var hazard = button.dataset.hazard;
                if (!hazard) { return; }
                var level = nationalMaxLevel(hazard, currentDayIndex);
                if (level > 0) {
                    button.style.boxShadow = 'inset 0 0 0 2px ' + levelInfo(hazard, level).color;
                } else {
                    button.style.boxShadow = '';
                }
            });
        }

        // Trait de côte coloré par le niveau d'alerte Littoral de chaque
        // département côtier — visible uniquement sur l'onglet Littoral (les
        // autres aléas gardent le seul remplissage à plat des départements),
        // demandé explicitement pour repérer l'alerte d'un coup d'œil sur la
        // ligne de côte plutôt que sur l'aplat du département entier.
        function paintLittoralOverlay() {
            if (!littoralOverlayGroup) { return; }
            littoralOverlayGroup.replaceChildren();
            if (currentHazard !== 'littoral' || !littoralRuns.length) {
                littoralOverlayGroup.style.display = 'none';
                return;
            }
            littoralOverlayGroup.style.display = '';
            littoralRuns.forEach(function (run) {
                var level = departmentLevel(run.code, 'littoral', currentDayIndex);
                var color = levelInfo('littoral', level).color;
                var d = run.points.map(function (xy, index) {
                    return (index === 0 ? 'M' : 'L') + xy[0].toFixed(2) + ',' + xy[1].toFixed(2);
                }).join(' ');
                var width = level > 0 ? (10 + level * 2) : 3;
                // Le style est posé via l'attribut `style` (pas `stroke`/
                // `stroke-width` en attributs de présentation) : la feuille
                // de styles a une règle générale `.hrw-map path { stroke:
                // ...; stroke-width: 1; }` qui s'applique à TOUS les <path>
                // de la carte, trait littoral compris — en SVG, une règle
                // CSS prime toujours sur un attribut de présentation, même
                // posé après coup en JS, donc `setAttribute('stroke', ...)`
                // était silencieusement écrasé par cette règle. `style`
                // inline a une priorité supérieure à la feuille de styles et
                // n'est pas concerné par ce piège.
                if (level > 0) {
                    // Liseré sombre sous le trait coloré : sur une carte de
                    // la France entière (viewBox 1000, rendue sur quelques
                    // centaines de pixels), un trait fin de la couleur du
                    // palier se fondait dans le fond clair et la frontière
                    // départementale déjà présente au même endroit — trop
                    // discret pour être vu sans zoomer fortement.
                    var casing = createSvgElement('path', { d: d, fill: 'none' });
                    casing.style.stroke = '#1c1f26';
                    casing.style.strokeWidth = (width + 4) + 'px';
                    casing.style.strokeLinecap = 'round';
                    casing.style.strokeLinejoin = 'round';
                    littoralOverlayGroup.appendChild(casing);
                }
                var path = createSvgElement('path', { d: d, fill: 'none' });
                path.style.stroke = level > 0 ? color : '#5b6b7a';
                path.style.strokeWidth = width + 'px';
                path.style.strokeLinecap = 'round';
                path.style.strokeLinejoin = 'round';
                path.style.opacity = level > 0 ? 1 : 0.55;
                littoralOverlayGroup.appendChild(path);
            });
        }

        // Le pire niveau trouvé n'importe où en France pour l'aléa/jour
        // courants — un indicateur national, pas celui d'un département
        // (peu importe lequel est sélectionné). Avant ce correctif le
        // texte était figé sur « 0/N » quel que soit le contenu réel de la
        // carte.
        function nationalMaxLevel(hazard, dayIndex) {
            var max = 0;
            if (!manifest || !manifest.departments) { return max; }
            Object.keys(manifest.departments).forEach(function (code) {
                var level = departmentLevel(code, hazard, dayIndex);
                if (level > max) { max = level; }
            });
            return max;
        }

        function updateLegendTitle() {
            if (!legendTitle) { return; }
            var maxLevel = maxLevelFor(currentHazard);
            var label = hazardLabel(currentHazard);
            var national = nationalMaxLevel(currentHazard, currentDayIndex);
            legendTitle.textContent = label + ' ' + national + '/' + maxLevel;
        }

        function buildLegend() {
            // L'échelle (nombre de paliers, libellés) dépend de l'aléa
            // affiché — la légende est donc reconstruite à chaque
            // changement d'aléa plutôt que dessinée une seule fois.
            legend.replaceChildren();
            var maxLevel = maxLevelFor(currentHazard);
            updateLegendTitle();
            for (var level = 0; level <= maxLevel; level++) {
                var info = levelInfo(currentHazard, level);
                var item = document.createElement('div');
                item.className = 'hrw-legend-item';
                var swatch = document.createElement('span');
                swatch.className = 'hrw-legend-swatch';
                swatch.style.backgroundColor = info.color;
                var label = document.createElement('span');
                label.textContent = info.label;
                item.appendChild(swatch);
                item.appendChild(label);
                legend.appendChild(item);
            }
        }

        function buildHazardTabs() {
            hazardTabs.replaceChildren();
            if (!manifest || !manifest.hazards) { return; }
            Object.keys(manifest.hazards).forEach(function (hazard) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'hrw-tab';
                button.dataset.hazard = hazard;
                button.appendChild(buildIconNode(hazard, 'hrw-tab-icon'));
                button.appendChild(document.createTextNode(manifest.hazards[hazard]));
                button.classList.toggle('is-active', hazard === currentHazard);
                button.addEventListener('click', function () {
                    setHazard(hazard);
                });
                hazardTabs.appendChild(button);
            });
        }

        function buildDayTabs() {
            dayTabs.replaceChildren();
            var department = manifest && manifest.departments ? manifest.departments[selectedDepartment || Object.keys(manifest.departments)[0]] : null;
            var daily = department ? department.daily : [];
            var formatter = dayFormatter();
            var labels = ['J0', 'J+1', 'J+2', 'J+3', 'J+4'];
            daily.forEach(function (entry, index) {
                var date = new Date(entry.date + 'T12:00:00Z');
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'hrw-tab';
                button.textContent = (labels[index] || ('J' + index)) + ' · ' + formatter.format(date);
                button.classList.toggle('is-active', index === currentDayIndex);
                button.addEventListener('click', function () {
                    setDay(index);
                });
                dayTabs.appendChild(button);
            });
        }

        function setHazard(hazard) {
            currentHazard = hazard;
            detailHazard = hazard;
            Array.prototype.forEach.call(hazardTabs.children, function (button) {
                button.classList.toggle('is-active', button.dataset.hazard === hazard);
            });
            buildLegend();
            paintMap();
            renderDetail();
        }

        function setDay(index) {
            currentDayIndex = index;
            Array.prototype.forEach.call(dayTabs.children, function (button, i) {
                button.classList.toggle('is-active', i === index);
            });
            paintMap();
            updateLegendTitle();
            renderDetail();
            renderNationalSummary();
        }

        function selectDepartment(code) {
            if (!manifest || !manifest.departments[code]) {
                return;
            }
            selectedDepartment = code;
            paintMap();
            updateLegendTitle();
            buildDayTabs();
            renderDetail();
        }

        function renderDetail() {
            if (!selectedDepartment || !manifest) {
                detailPlaceholder.hidden = false;
                detailContent.hidden = true;
                return;
            }
            var department = manifest.departments[selectedDepartment];
            if (!department || !department.daily[currentDayIndex]) {
                detailPlaceholder.hidden = false;
                detailContent.hidden = true;
                return;
            }
            detailPlaceholder.hidden = true;
            detailContent.hidden = false;

            var name = namesByCode[selectedDepartment] || selectedDepartment;
            detailTitle.textContent = name + ' (' + selectedDepartment + ')';

            var hazards = department.daily[currentDayIndex].hazards || {};
            detailGrid.replaceChildren();
            Object.keys(manifest.hazards).forEach(function (hazard) {
                var level = hazards[hazard] || 0;
                var info = levelInfo(hazard, level);
                var cell = document.createElement('div');
                cell.className = 'hrw-hazard-cell';
                cell.classList.toggle('is-active', hazard === detailHazard);
                var name2 = document.createElement('span');
                name2.className = 'hrw-hazard-name';
                name2.appendChild(buildIconNode(hazard, 'hrw-hazard-icon'));
                name2.appendChild(document.createTextNode(manifest.hazards[hazard]));
                var levelSpan = document.createElement('span');
                levelSpan.className = 'hrw-hazard-level';
                levelSpan.style.backgroundColor = info.color;
                levelSpan.style.color = info.text_color;
                // Pas de « (X/N) » ici : la case est trop étroite pour
                // l'empiler avec un libellé à seuil déjà entre parenthèses
                // (ex. « Modérée (≥ 28 °C) (2/7) ») — illisible, deux
                // groupes de parenthèses collés. Le rang complet reste
                // visible dans l'infobulle de la carte et celle de la
                // frise. Le mot et le seuil sont en plus séparés sur deux
                // lignes (mot en gras, seuil plus petit) : à la suite sur
                // une seule ligne, ça restait illisible dans une case
                // aussi étroite même sans le suffixe.
                var parts = splitHazardLabel(info.label);
                var mainLine = document.createElement('span');
                mainLine.className = 'hrw-hazard-level-main';
                mainLine.textContent = parts.main;
                levelSpan.appendChild(mainLine);
                if (parts.sub) {
                    levelSpan.appendChild(document.createElement('br'));
                    var subLine = document.createElement('span');
                    subLine.className = 'hrw-hazard-level-sub';
                    subLine.textContent = parts.sub;
                    levelSpan.appendChild(subLine);
                }
                cell.appendChild(name2);
                cell.appendChild(document.createElement('br'));
                cell.appendChild(levelSpan);
                cell.addEventListener('click', function () {
                    detailHazard = hazard;
                    renderDetail();
                });
                detailGrid.appendChild(cell);
            });

            renderFrise(department);
        }

        function renderAdvice(level) {
            if (!adviceText) { return; }
            // Rien à afficher au niveau Nul (0) : pas d'alerte, pas de
            // conseil à donner.
            if (!level) {
                if (adviceBox) { adviceBox.hidden = true; }
                adviceText.textContent = '';
                return;
            }
            if (adviceBox) { adviceBox.hidden = false; }

            // Palier léger/modéré/sévère choisi selon la position relative
            // du niveau dans l'échelle propre à l'aléa (4 à 9 paliers selon
            // les cas, donc un simple découpage en tiers plutôt que des
            // seuils absolus).
            var maxLevel = maxLevelFor(detailHazard);
            var ratio = maxLevel > 0 ? level / maxLevel : 1;
            var tierIndex = ratio <= 1 / 3 ? 0 : (ratio <= 2 / 3 ? 1 : 2);
            var tiers = ADVICE_TIERS[detailHazard] || [];
            var message = tiers[tierIndex] || tiers[tiers.length - 1] || '';

            if (detailHazard === 'feu') {
                message += ' ' + FEU_DISCLAIMER;
            } else if (detailHazard === 'littoral') {
                message += ' ' + LITTORAL_DISCLAIMER;
            }
            adviceText.textContent = message;
        }

        function renderFrise(department) {
            friseHazardLabel.textContent = hazardLabel(detailHazard);
            friseTrack.replaceChildren();
            if (friseLabels) { friseLabels.replaceChildren(); }

            var dayEntry = department.daily[currentDayIndex];
            if (!dayEntry) { return; }

            var hourlyAll = department.hourly || [];
            var dayHours = hourlyAll.filter(function (entry) {
                return zonedDateKey(entry.time, timezone) === dayEntry.date;
            });
            if (!dayHours.length) {
                if (adviceText) {
                    adviceText.textContent = 'Données HARMONIE indisponibles pour cette journée.';
                }
                return;
            }

            // La frise doit toujours partir de 6h (début de la journée
            // météo), même le jour où le run HARMONIE lui-même n'a démarré
            // que plus tard (ex. un run lancé à 9h ne peut pas avoir de
            // données pour 6h-8h ce jour-là) — sinon la première case
            // affichée n'était pas 6h mais l'heure de départ réelle du run,
            // ce qui semblait être un bug. On construit donc les 24 cases
            // une par une par heure locale, avec une case « pas de
            // données » pour les heures manquantes, plutôt que de se
            // contenter des entrées réellement présentes.
            var hourMap = {};
            dayHours.forEach(function (entry) {
                hourMap[localHourOf(new Date(entry.time))] = entry;
            });

            var lastIndex = hourlyAll.indexOf(dayHours[dayHours.length - 1]);
            var closingEntry = lastIndex >= 0 ? hourlyAll[lastIndex + 1] : null;

            var formatter = hourFormatter();

            function appendCell(hourLabel, entry) {
                var cell = document.createElement('div');
                cell.className = 'hrw-frise-hour';
                if (entry) {
                    var level = (entry.hazards || {})[detailHazard] || 0;
                    var info = levelInfo(detailHazard, level);
                    cell.style.backgroundColor = info.color;
                    cell.title = formatter.format(new Date(entry.time)) + ' — ' +
                        hazardLabel(detailHazard) + ' : ' + info.label + levelSuffix(detailHazard, level);
                } else {
                    cell.classList.add('hrw-frise-hour-empty');
                    cell.title = 'Données indisponibles pour cette heure (avant le début du run).';
                }
                friseTrack.appendChild(cell);

                if (friseLabels) {
                    var tick = document.createElement('span');
                    tick.className = 'hrw-frise-tick';
                    if (hourLabel % 3 === 0) {
                        tick.textContent = hourLabel + 'h';
                    }
                    friseLabels.appendChild(tick);
                }
            }

            // Journée « météo » 6h → 6h (pas minuit → minuit) : l'ordre
            // d'affichage suit ce même décalage, sinon les heures 0h-5h du
            // lendemain (incluses dans CETTE journée par zonedDateKey)
            // apparaîtraient avant 6h-23h alors qu'elles sont
            // chronologiquement après.
            for (var hour = 6; hour <= 23; hour++) {
                appendCell(hour, hourMap[hour] || null);
            }
            for (var hour2 = 0; hour2 <= 5; hour2++) {
                appendCell(hour2, hourMap[hour2] || null);
            }
            // Case de clôture « 6h » du lendemain, pour boucler l'affichage
            // 6h → 5h → 6h.
            appendCell(6, closingEntry);

            renderAdvice(dayEntry.hazards[detailHazard] || 0);
        }

        // --- Petit résumé national (records du jour J0 : maxi/mini de
        // température, rafale maxi, cumul de pluie maxi, chacun avec le
        // département qui le détient). Toujours J0, indépendant de l'onglet
        // jour actif — appelé une fois après le chargement des données.
        function renderNationalSummary() {
            if (!nationalSummaryBox) { return; }
            var entry = manifest && Array.isArray(manifest.national_summary)
                ? manifest.national_summary[currentDayIndex]
                : null;
            if (!entry) {
                nationalSummaryBox.hidden = true;
                return;
            }

            function label(field, unit, decimals) {
                if (!field) { return '—'; }
                var deptName = namesByCode[field.department] || field.department;
                return field.value.toFixed(decimals) + unit + ' (' + deptName + ')';
            }

            // Seuils d'alerte visuelle (pas les seuils de vigilance officielle,
            // juste un repère pour attirer l'œil sur une valeur nationale du
            // jour qui sort du lot). « extreme » = valeur au-delà du seuil ;
            // « bas » pour le mini uniquement, où c'est le froid qui est
            // extrême, pas la chaleur.
            function markExtreme(el, field, isExtreme) {
                if (!el) { return; }
                el.classList.toggle('hrw-summary-extreme', !!(field && isExtreme(field.value)));
            }

            if (summaryTitle) {
                var labels = ['J0', 'J+1', 'J+2', 'J+3', 'J+4'];
                var dayLabel = labels[currentDayIndex] || ('J' + currentDayIndex);
                var dateText = '';
                if (entry.date) {
                    var date = new Date(entry.date + 'T12:00:00Z');
                    dateText = ' · ' + dayFormatter().format(date);
                }
                summaryTitle.textContent = 'France — ' + dayLabel + dateText;
            }
            if (summaryMax) {
                summaryMax.textContent = label(entry.max_temperature, '°C', 1);
                markExtreme(summaryMax, entry.max_temperature, function (v) { return v >= 35; });
            }
            if (summaryMin) {
                summaryMin.textContent = label(entry.min_temperature, '°C', 1);
                markExtreme(summaryMin, entry.min_temperature, function (v) { return v <= -5; });
            }
            if (summaryGust) {
                summaryGust.textContent = label(entry.max_gust, ' km/h', 0);
                markExtreme(summaryGust, entry.max_gust, function (v) { return v >= 100; });
            }
            if (summaryPrecip) {
                summaryPrecip.textContent = label(entry.max_precip, ' mm', 1);
                markExtreme(summaryPrecip, entry.max_precip, function (v) { return v >= 50; });
            }
            nationalSummaryBox.hidden = false;
        }

        // --- Info-bulle au survol d'un département (nom, niveau de l'aléa
        // affiché, mini-frise de la journée sélectionnée) — indépendante du
        // clic, qui ouvre lui le panneau de détail complet.
        var tooltip = document.createElement('div');
        tooltip.className = 'hrw-map-tooltip';
        tooltip.hidden = true;
        if (mapWrap) { mapWrap.appendChild(tooltip); }

        function positionTooltip(anchorEl) {
            if (!mapWrap) { return; }
            var wrapRect = mapWrap.getBoundingClientRect();
            var anchorRect = anchorEl.getBoundingClientRect();
            var x = anchorRect.left + anchorRect.width / 2 - wrapRect.left;
            var y = anchorRect.top - wrapRect.top;

            // Le CSS applique translate(-50%, -100% - 10px) : le clamp
            // précédent ne bornait que la propriété "left" elle-même, pas
            // le décalage supplémentaire de moitié-largeur/hauteur que le
            // transform applique ensuite — un département à l'extrême
            // gauche de la carte (ex. Gironde) faisait ainsi déborder la
            // bulle hors écran (left négatif, coupée). On mesure la taille
            // réelle de la bulle (déjà remplie, juste rendue visible) pour
            // borner sa boîte finale plutôt que son seul point d'ancrage.
            tooltip.style.left = x + 'px';
            tooltip.style.top = Math.max(8, y) + 'px';
            var halfWidth = tooltip.offsetWidth / 2;
            var minX = halfWidth + 4;
            var maxX = wrapRect.width - halfWidth - 4;
            var clampedX = maxX >= minX ? Math.min(Math.max(x, minX), maxX) : wrapRect.width / 2;
            tooltip.style.left = clampedX + 'px';

            var tooltipHeight = tooltip.offsetHeight;
            var minY = tooltipHeight + 14;
            tooltip.style.top = Math.max(minY, y) + 'px';
        }

        function showDeptTooltip(code, anchorEl) {
            if (!manifest || !manifest.departments[code]) { return; }
            var department = manifest.departments[code];
            var dayEntry = department.daily[currentDayIndex];
            if (!dayEntry) { return; }
            var level = (dayEntry.hazards || {})[currentHazard] || 0;
            var info = levelInfo(currentHazard, level);

            tooltip.replaceChildren();
            var title = document.createElement('div');
            title.className = 'hrw-tooltip-title';
            title.textContent = (namesByCode[code] || code) + ' (' + code + ')';
            tooltip.appendChild(title);

            var chip = document.createElement('div');
            chip.className = 'hrw-tooltip-chip';
            chip.style.backgroundColor = info.color;
            chip.style.color = info.text_color;
            chip.textContent = hazardLabel(currentHazard) + ' — ' + info.label + levelSuffix(currentHazard, level);
            tooltip.appendChild(chip);

            var hourlyAll = department.hourly || [];
            var dayHours = hourlyAll.filter(function (entry) {
                return zonedDateKey(entry.time, timezone) === dayEntry.date;
            });
            if (dayHours.length) {
                var mini = document.createElement('div');
                mini.className = 'hrw-tooltip-frise';
                dayHours.forEach(function (entry) {
                    var hourLevel = (entry.hazards || {})[currentHazard] || 0;
                    var segment = document.createElement('span');
                    segment.style.backgroundColor = levelInfo(currentHazard, hourLevel).color;
                    mini.appendChild(segment);
                });
                tooltip.appendChild(mini);

                // Repères positionnés en absolu (premier, milieu, dernier)
                // plutôt qu'une case par heure en flex : dans une info-bulle
                // de 180px avec 20-30 heures, une case flex par heure était
                // trop étroite pour son propre texte, qui débordait sur les
                // voisines et devenait illisible (ex. « 22h » × 2 superposés
                // rendus comme « 2222h »).
                var miniLabels = document.createElement('div');
                miniLabels.className = 'hrw-tooltip-frise-labels';
                var lastIdx = dayHours.length - 1;
                var tickIndexes = lastIdx > 0
                    ? Array.from(new Set([0, Math.round(lastIdx / 2), lastIdx]))
                    : [0];
                tickIndexes.forEach(function (idx) {
                    var tick = document.createElement('span');
                    tick.className = 'hrw-tooltip-frise-tick-abs';
                    tick.textContent = localHourOf(new Date(dayHours[idx].time)) + 'h';
                    var pct = lastIdx > 0 ? (idx / lastIdx) * 100 : 50;
                    tick.style.left = pct + '%';
                    if (idx === 0) {
                        tick.style.transform = 'translateX(0)';
                    } else if (idx === lastIdx) {
                        tick.style.transform = 'translateX(-100%)';
                    } else {
                        tick.style.transform = 'translateX(-50%)';
                    }
                    miniLabels.appendChild(tick);
                });
                tooltip.appendChild(miniLabels);
            }

            // Rendre visible AVANT de positionner : positionTooltip() a
            // besoin de mesurer la largeur/hauteur réelle de la bulle
            // (offsetWidth/offsetHeight), qui valent 0 tant que l'élément
            // est masqué via [hidden].
            tooltip.hidden = false;
            positionTooltip(anchorEl);
        }

        function hideDeptTooltip() {
            tooltip.hidden = true;
        }

        function buildMapInto(svgEl, features, viewSize, padding, suppressIconCodes, iconRadius) {
            if (!svgEl || !features.length) { return; }
            var bounds = computeBoundsFromFeatures(features);
            var project = buildProjector(bounds, viewSize, padding);
            features.forEach(function (feature) {
                var code = String((feature.properties || {}).code || '').toUpperCase();
                var name = (feature.properties || {}).nom || code;
                if (!code) { return; }
                namesByCode[code] = name;

                var path = document.createElementNS(SVG_NS, 'path');
                path.setAttribute('d', pathForGeometry(feature.geometry, project));
                path.setAttribute('data-code', code);
                path.setAttribute('role', 'button');
                path.setAttribute('tabindex', '0');
                path.setAttribute('aria-label', name);
                path.addEventListener('click', function () {
                    selectDepartment(code);
                });
                path.addEventListener('keydown', function (event) {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        selectDepartment(code);
                    }
                });
                path.addEventListener('mouseenter', function () { showDeptTooltip(code, path); });
                path.addEventListener('mouseleave', hideDeptTooltip);
                path.addEventListener('focus', function () { showDeptTooltip(code, path); });
                path.addEventListener('blur', hideDeptTooltip);
                svgEl.appendChild(path);

                var ringPoints = largestExteriorRingPoints(feature.geometry, project);
                var centroid = ringPoints.length ? polygonCentroid(ringPoints) : [0, 0];

                // Badge blanc + icône monochrome par-dessus, plutôt qu'un
                // glyphe nu : reste lisible quelle que soit la couleur
                // pastel du département en dessous.
                var iconGroup = createSvgElement('g', { class: 'hrw-dept-icon-wrap' });
                iconGroup.style.display = 'none';
                var badge = createSvgElement('circle', {
                    class: 'hrw-dept-icon-badge',
                    cx: centroid[0].toFixed(2),
                    cy: centroid[1].toFixed(2),
                    r: iconRadius
                });
                var glyphScale = (iconRadius * 1.25) / 24;
                var glyphX = centroid[0] - 12 * glyphScale;
                var glyphY = centroid[1] - 12 * glyphScale;
                var glyph = createSvgElement('g', {
                    class: 'hrw-dept-icon',
                    transform: 'translate(' + glyphX.toFixed(2) + ',' + glyphY.toFixed(2) + ') scale(' + glyphScale.toFixed(3) + ')'
                });
                iconGroup.appendChild(badge);
                iconGroup.appendChild(glyph);
                svgEl.appendChild(iconGroup);

                if (!mapEntries[code]) { mapEntries[code] = []; }
                mapEntries[code].push({
                    path: path,
                    iconGroup: iconGroup,
                    glyph: glyph,
                    showIcon: suppressIconCodes.indexOf(code) === -1
                });
            });
        }

        function buildMap(geojson, coastGeojson) {
            var features = geojson.features || [];
            buildMapInto(mapSvg, features, 1000, 12, IDF_CODES, 13);

            var idfFeatures = features.filter(function (feature) {
                var code = String((feature.properties || {}).code || '').toUpperCase();
                return IDF_CODES.indexOf(code) !== -1;
            });
            buildMapInto(insetSvg, idfFeatures, 300, 14, [], 17);

            littoralOverlayGroup = createSvgElement('g', { 'pointer-events': 'none' });
            mapSvg.appendChild(littoralOverlayGroup);
            if (coastGeojson) {
                var bounds = computeBoundsFromFeatures(features);
                var project = buildProjector(bounds, 1000, 12);
                littoralRuns = buildLittoralRuns(features, coastGeojson, project);
            }

            mapLoading.hidden = true;
        }

        function composeMapCanvas() {
            return new Promise(function (resolve, reject) {
                var rect = mapSvg.getBoundingClientRect();
                var width = Math.max(1, Math.round(rect.width || 1000));
                var height = Math.max(1, Math.round(rect.height || 1000));
                var clone = mapSvg.cloneNode(true);
                clone.setAttribute('width', width);
                clone.setAttribute('height', height);
                clone.setAttribute('xmlns', SVG_NS);
                var svgText = new XMLSerializer().serializeToString(clone);
                var svgBlob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' });
                var url = URL.createObjectURL(svgBlob);
                var image = new Image();
                image.onload = function () {
                    var canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    var context = canvas.getContext('2d');
                    context.fillStyle = '#ffffff';
                    context.fillRect(0, 0, width, height);
                    context.drawImage(image, 0, 0, width, height);
                    URL.revokeObjectURL(url);
                    resolve(canvas);
                };
                image.onerror = function () {
                    URL.revokeObjectURL(url);
                    reject(new Error('Rendu SVG indisponible'));
                };
                image.src = url;
            });
        }

        function exportFilename(extension) {
            function two(number) { return String(number).padStart(2, '0'); }
            var now = new Date();
            var stamp = now.getFullYear() + two(now.getMonth() + 1) + two(now.getDate()) +
                '-' + two(now.getHours()) + two(now.getMinutes()) + two(now.getSeconds());
            return 'vigilance-' + currentHazard + '-' + stamp + '.' + extension;
        }

        if (captureButton) {
            captureButton.addEventListener('click', function () {
                composeMapCanvas().then(function (canvas) {
                    canvas.toBlob(function (blob) {
                        if (!blob) { return; }
                        var url = URL.createObjectURL(blob);
                        var link = document.createElement('a');
                        link.href = url;
                        link.download = exportFilename('png');
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        window.setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
                    }, 'image/png');
                }).catch(function () {});
            });
        }

        if (copyButton) {
            copyButton.addEventListener('click', function () {
                if (!navigator.clipboard || !window.ClipboardItem) {
                    return;
                }
                composeMapCanvas().then(function (canvas) {
                    canvas.toBlob(function (blob) {
                        if (!blob) { return; }
                        navigator.clipboard.write([
                            new window.ClipboardItem({ 'image/png': blob })
                        ]).catch(function () {});
                    }, 'image/png');
                }).catch(function () {});
            });
        }

        // --- Recherche commune + géolocalisation (même API que le tableau
        // HARMONIE : geo.api.gouv.fr).
        function closeResults() {
            searchResults.hidden = true;
            searchResults.replaceChildren();
        }

        function displaySearchResults(candidates) {
            searchResults.replaceChildren();
            if (!candidates.length) {
                closeResults();
                return;
            }
            candidates.forEach(function (candidate) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'hrw-search-result';
                button.textContent = candidate.nom + ' (' + (candidate.codeDepartement || '') + ')';
                button.addEventListener('click', function () {
                    input.value = candidate.nom;
                    closeResults();
                    selectDepartment(String(candidate.codeDepartement || '').toUpperCase());
                });
                searchResults.appendChild(button);
            });
            searchResults.hidden = false;
        }

        function searchCommunes(query) {
            if (searchController) {
                searchController.abort();
            }
            searchController = new AbortController();
            var parameters = new URLSearchParams({
                fields: 'nom,code,codeDepartement,population',
                format: 'json',
                boost: 'population',
                limit: '10'
            });
            if (/^\d{5}$/.test(query)) {
                parameters.set('codePostal', query);
            } else {
                parameters.set('nom', query);
            }
            fetchJson(COMMUNES_API + '?' + parameters.toString(), { signal: searchController.signal })
                .then(function (payload) {
                    displaySearchResults(Array.isArray(payload) ? payload : []);
                })
                .catch(function (error) {
                    if (error.name === 'AbortError') { return; }
                    closeResults();
                });
        }

        if (input) {
            input.addEventListener('input', function () {
                var query = input.value.trim();
                window.clearTimeout(debounceTimer);
                if (query.length < 2) {
                    closeResults();
                    return;
                }
                debounceTimer = window.setTimeout(function () {
                    searchCommunes(query);
                }, 220);
            });
            document.addEventListener('click', function (event) {
                if (!app.contains(event.target)) { return; }
                if (!event.target.closest('.hrw-search')) {
                    closeResults();
                }
            });
        }

        if (locateButton) {
            locateButton.addEventListener('click', function () {
                if (!navigator.geolocation) { return; }
                locateButton.disabled = true;
                locateButton.textContent = '📍 Localisation…';
                navigator.geolocation.getCurrentPosition(function (position) {
                    var parameters = new URLSearchParams({
                        lat: String(position.coords.latitude),
                        lon: String(position.coords.longitude),
                        fields: 'nom,code,codeDepartement',
                        format: 'json'
                    });
                    fetchJson(COMMUNES_API + '?' + parameters.toString())
                        .then(function (payload) {
                            var candidates = Array.isArray(payload) ? payload : (payload ? [payload] : []);
                            if (!candidates.length) {
                                throw new Error('Position hors couverture');
                            }
                            var candidate = candidates[0];
                            if (input) {
                                input.value = candidate.nom;
                            }
                            selectDepartment(String(candidate.codeDepartement || '').toUpperCase());
                        })
                        .catch(function () {})
                        .then(function () {
                            locateButton.disabled = false;
                            locateButton.textContent = '📍 Me géolocaliser';
                        });
                }, function () {
                    locateButton.disabled = false;
                    locateButton.textContent = '📍 Me géolocaliser';
                });
            });
        }

        // --- Chargement initial.
        if (window.HRW_AUTOHEAL && window.HRW_AUTOHEAL.url) {
            fetch(window.HRW_AUTOHEAL.url, { method: 'POST', cache: 'no-store' }).catch(function () {});
        }

        if (!baseUrl) {
            mapLoading.textContent = 'Adresse des données de risques non configurée.';
            return;
        }

        widenToFitAncestor(app);
        var widenTimer = null;
        function scheduleWiden() {
            window.clearTimeout(widenTimer);
            widenTimer = window.setTimeout(function () {
                widenToFitAncestor(app);
            }, 150);
        }
        window.addEventListener('resize', scheduleWiden);

        // Les délais fixes ci-dessous ne suffisent pas si la mise en page
        // du thème bouge après coup (polices qui finissent de charger,
        // widgets Avada chargés en différé, etc.) : on observe aussi la
        // largeur réelle des ancêtres pour relancer l'agrandissement à
        // chaque changement, sans dépendre d'un minutage fixe.
        if (window.ResizeObserver) {
            var widenObserver = new ResizeObserver(scheduleWiden);
            var observedEl = app.parentElement;
            var observedHops = 0;
            while (observedEl && observedHops < 6) {
                widenObserver.observe(observedEl);
                observedEl = observedEl.parentElement;
                observedHops += 1;
            }
        }

        Promise.all([
            fetchJson(baseUrl + '/risques.json'),
            fetchText(geojsonUrl).then(function (text) { return JSON.parse(text); }),
            littoralUrl
                ? fetchText(littoralUrl).then(function (text) { return JSON.parse(text); }).catch(function () { return null; })
                : Promise.resolve(null)
        ]).then(function (results) {
            manifest = results[0];
            var geojson = results[1];
            var coastGeojson = results[2];
            if (!manifest || manifest.status !== 'ok') {
                throw new Error('Manifeste de risques invalide');
            }
            buildMap(geojson, coastGeojson);
            buildLegend();
            buildHazardTabs();
            buildDayTabs();
            paintMap();
            renderNationalSummary();

            if (manifest.run_time) {
                var runDate = new Date(manifest.run_time);
                runMeta.textContent = 'Run HARMONIE-AROME du ' +
                    new Intl.DateTimeFormat('fr-FR', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'UTC'
                    }).format(runDate) + ' UTC (Run ' + zNotation(runDate) + ')';
            }
            if (manifest.generated_at) {
                generated.textContent = 'Risques calculés le ' +
                    new Intl.DateTimeFormat('fr-FR', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                    }).format(new Date(manifest.generated_at));
            }

            if (selectedDepartment && manifest.departments[selectedDepartment]) {
                selectDepartment(selectedDepartment);
            }

            [300, 1000, 2500].forEach(function (delay) {
                window.setTimeout(function () { widenToFitAncestor(app); }, delay);
            });

            scheduleNextDayBoundaryReload();
        }).catch(function (error) {
            mapLoading.textContent = 'Les données de vigilance ne sont pas encore disponibles : ' + error.message;
        });
    }

    whenReady(function () {
        document.querySelectorAll('[data-hrw-app]').forEach(initApp);
    });
}());
