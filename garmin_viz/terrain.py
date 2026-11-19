"""Carte 3D avec relief réel (MapLibre GL JS), sans clé API.

- Relief : tuiles d'élévation AWS Terrain Tiles (format terrarium)
- Fonds : satellite Esri World Imagery, plan OpenStreetMap, ou topo OpenTopoMap
- La trace est drapée sur le terrain et colorée selon la métrique choisie.
- Survol : flèche qui avance, trait plein derrière, compteur en direct, barre de progression.
"""
import json

import numpy as np
import plotly.colors as pc

from .plots import METRICS

BASEMAPS = {
    "Satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                  "Imagery © Esri", 19),
    "Plan OSM": ("https://tile.openstreetmap.org/{z}/{x}/{y}.png", "© OpenStreetMap", 19),
    "Topo": ("https://tile.opentopomap.org/{z}/{x}/{y}.png", "© OpenTopoMap, © OSM", 17),
}


def _clean(series, nd=1):
    """Liste JSON-safe (NaN -> null)."""
    return [None if v != v else round(float(v), nd) for v in series]


def _prepare(df, metric, max_points=1500):
    g = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    if len(g) > max_points:  # allège les très longues sorties
        g = g.iloc[np.linspace(0, len(g) - 1, max_points).astype(int)].reset_index(drop=True)
    label, k, cmap = METRICS[metric]
    v = (g[metric] * k).to_numpy(float)
    lo, hi = np.nanpercentile(v, 5), np.nanpercentile(v, 95)
    t = np.clip((np.nan_to_num(v, nan=lo) - lo) / max(hi - lo, 1e-9), 0, 1)
    colors = pc.sample_colorscale(cmap, list(t))
    feats = [{
        "type": "Feature",
        "properties": {"color": colors[i], "i": i},
        "geometry": {"type": "LineString",
                     "coordinates": [[g.lon[i], g.lat[i]], [g.lon[i + 1], g.lat[i + 1]]]},
    } for i in range(len(g) - 1)]
    info = {
        "t": _clean((g["time"] - g["time"].iloc[0]).dt.total_seconds(), 0),
        "d": _clean(g["distance"] / 1000, 2),
        "v": _clean(g["speed"] * 3.6, 1),
        "hr": _clean(g["hr"], 0),
        "alt": _clean(g["alt"], 0),
    }
    coords = [[float(a), float(b)] for a, b in zip(g.lon, g.lat)]
    return {"type": "FeatureCollection", "features": feats}, coords, info, label, (lo, hi), cmap


TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
 html,body,#map{margin:0;height:__H__px;width:100%;font-family:system-ui,sans-serif}
 .ui{position:absolute;z-index:2;top:10px;left:10px;background:#fffe;padding:8px 10px;border-radius:8px;font-size:12px;width:230px;box-shadow:0 1px 4px #0004}
 .ui button,.ui select{cursor:pointer;margin-right:4px}
 .legend{height:10px;background:linear-gradient(to right,__BAR__);margin:4px 0 2px}
 .row{display:flex;justify-content:space-between}
 #slider{width:100%;margin:8px 0 2px}
 .live{display:grid;grid-template-columns:1fr 1fr;gap:2px 8px;margin-top:6px;font-variant-numeric:tabular-nums}
 .live b{font-size:15px}
 .live small{color:#666;display:block;font-size:10px}
 .arrow{width:34px;height:34px;filter:drop-shadow(0 0 3px #000)}
</style></head><body>
<div id="map"></div>
<div class="ui">
  <button id="fly">▶ Survol</button>
  <select id="speed"><option value="1">x1</option><option value="2" selected>x2</option><option value="4">x4</option><option value="8">x8</option></select>
  <button id="reset">Vue d'ensemble</button>
  <div style="margin-top:6px"><b>__LABEL__</b></div>
  <div class="legend"></div><div class="row"><span>__LO__</span><span>__HI__</span></div>
  <input id="slider" type="range" min="0" max="0" value="0">
  <div id="dbg" style="margin-top:6px;font-size:10px;color:#888">carte v4</div>
  <div class="live">
    <div><b id="o_t">0:00</b><small>temps</small></div>
    <div><b id="o_d">0.00 km</b><small>distance</small></div>
    <div><b id="o_v">-</b><small>vitesse</small></div>
    <div><b id="o_hr">-</b><small>FC</small></div>
    <div><b id="o_alt">-</b><small>altitude</small></div>
    <div><b id="o_pace">-</b><small>allure</small></div>
  </div>
</div>
<script>
const route = __ROUTE__, track = __TRACK__, bounds = __BOUNDS__, info = __INFO__;
const N = route.length;
const map = new maplibregl.Map({
  container: 'map', bounds: bounds, fitBoundsOptions: {padding:70, pitch:65, bearing:20}, maxPitch: 85,
  style: {
    version: 8,
    sources: {
      base: {type:'raster', tiles:['__TILES__'], tileSize:256, maxzoom:__MAXZ__, attribution:'__ATTRIB__'},
      dem: {type:'raster-dem', encoding:'terrarium', tileSize:256, maxzoom:15,
            tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
            attribution:'Terrain: AWS / Mapzen'},
      dem2: {type:'raster-dem', encoding:'terrarium', tileSize:256, maxzoom:15,
             tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png']},
      track: {type:'geojson', data:track},
      doneSrc: {type:'geojson', data:{type:'Feature', geometry:{type:'LineString', coordinates:[route[0], route[0]]}}}
    },
    layers: [
      {id:'base', type:'raster', source:'base'},
      {id:'hill', type:'hillshade', source:'dem2', paint:{'hillshade-exaggeration':0.35}},
      // trace complète, couleurs de la métrique (atténuée pendant le survol)
      {id:'full_casing', type:'line', source:'track', layout:{'line-cap':'round','line-join':'round'},
       paint:{'line-color':'#000','line-width':9,'line-opacity':0.5}},
      {id:'full', type:'line', source:'track', layout:{'line-cap':'round','line-join':'round'},
       paint:{'line-color':['get','color'],'line-width':5,'line-opacity':1}},
      // trait plein parcouru : jaune opaque, contour noir
      {id:'done_casing', type:'line', source:'doneSrc',
       layout:{'line-cap':'round','line-join':'round'}, paint:{'line-color':'#000','line-width':14,'line-opacity':1}},
      {id:'done', type:'line', source:'doneSrc',
       layout:{'line-cap':'round','line-join':'round'}, paint:{'line-color':'#ffd400','line-width':8,'line-opacity':1}}
    ],
    terrain: {source:'dem', exaggeration:__EXAG__}
  }
});
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}));
map.addControl(new maplibregl.ScaleControl());

// marqueurs de départ / arrivée
new maplibregl.Marker({color:'#2ecc71'}).setLngLat(route[0]).addTo(map);
new maplibregl.Marker({color:'#e74c3c'}).setLngLat(route[N-1]).addTo(map);

// flèche de progression (pointe vers le haut = nord, puis tournée selon le cap)
const el = document.createElement('div');
el.innerHTML = '<svg class="arrow" viewBox="0 0 34 34"><path d="M17 2 L30 31 L17 24 L4 31 Z" fill="#fff" stroke="#111" stroke-width="2.5" stroke-linejoin="round"/></svg>';
el.style.display = 'none';
const arrow = new maplibregl.Marker({element: el, rotationAlignment:'map', pitchAlignment:'viewport'})
  .setLngLat(route[0]).addTo(map);

const $ = id => document.getElementById(id);
map.on('error', e => { $('dbg').style.color = '#c00'; $('dbg').textContent = 'erreur : ' + ((e.error && e.error.message) || e.message || e); });
const slider = $('slider'); slider.max = N - 1;
let idx = 0, flying = false, heading = 0, following = false;

function bearingTo(a, b) { return Math.atan2(b[0]-a[0], b[1]-a[1]) * 180 / Math.PI; }
function fmtT(s) { s = Math.round(s); const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = s%60;
  return (h ? h + ':' + String(m).padStart(2,'0') : m) + ':' + String(x).padStart(2,'0'); }
function fmtPace(v) { if (!v || v < 1) return '-'; const s = 3600 / v; return Math.floor(s/60) + ':' + String(Math.round(s%60)).padStart(2,'0') + '/km'; }

function setDone(n) {
  const src = map.getSource('doneSrc'); if (!src) return;
  const c = n < 1 ? [route[0], route[0]] : route.slice(0, n + 1);
  src.setData({type:'Feature', geometry:{type:'LineString', coordinates:c}});
}

function show(i, moveCamera) {
  idx = i; slider.value = i;
  // trait plein jusqu'à la position actuelle, trace fantôme devant
  setDone(Math.max(1, i));
  map.setPaintProperty('full', 'line-opacity', 0.4);
  map.setPaintProperty('full_casing', 'line-opacity', 0.15);
  // cap lissé sur quelques points
  const a = route[Math.max(0, i-3)], b = route[Math.min(N-1, i+5)];
  if (a[0] !== b[0] || a[1] !== b[1]) {
    const target = bearingTo(a, b);
    const d = ((target - heading + 540) % 360) - 180; heading += d * 0.25;
  }
  el.style.display = 'block';
  arrow.setLngLat(route[i]).setRotation(heading);
  if (moveCamera) map.jumpTo({center: route[i], bearing: heading, pitch: 58, zoom: 14.8, padding: {bottom: 220, top: 0, left: 0, right: 0}});
  // compteur
  $('o_t').textContent = fmtT(info.t[i] || 0);
  $('o_d').textContent = (info.d[i] != null ? info.d[i].toFixed(2) : '-') + ' km';
  $('o_v').textContent = info.v[i] != null ? info.v[i].toFixed(1) + ' km/h' : '-';
  $('o_pace').textContent = fmtPace(info.v[i]);
  $('o_hr').textContent = info.hr[i] != null ? info.hr[i] + ' bpm' : '-';
  $('o_alt').textContent = info.alt[i] != null ? info.alt[i] + ' m' : '-';
}

function resetView() {
  flying = false; $('fly').textContent = '▶ Survol';
  setDone(0);
  map.setPaintProperty('full', 'line-opacity', 1); map.setPaintProperty('full_casing', 'line-opacity', 0.5);
  map.setPadding({top:0, bottom:0, left:0, right:0});
  el.style.display = 'none';
  map.fitBounds(bounds, {padding:70, pitch:65, bearing:20, duration:1200});
}

let acc = 0;
function step() {
  if (!flying) return;
  acc += parseFloat($('speed').value) * 0.6;       // points par image
  const adv = Math.floor(acc); acc -= adv;
  idx = Math.min(N - 1, idx + adv);
  show(idx, true);
  if (idx >= N - 1) { flying = false; $('fly').textContent = '↻ Rejouer'; return; }
  requestAnimationFrame(step);
}
$('fly').onclick = () => {
  if (flying) { flying = false; $('fly').textContent = '▶ Reprendre'; return; }  // pause
  if (idx >= N - 1) idx = 0;
  flying = true; $('fly').textContent = '⏸ Pause'; heading = bearingTo(route[0], route[Math.min(8, N-1)]);
  requestAnimationFrame(step);
};
$('reset').onclick = () => { idx = 0; slider.value = 0; resetView(); };
slider.oninput = () => { flying = false; $('fly').textContent = '▶ Reprendre'; show(parseInt(slider.value), true); };
</script></body></html>"""


def terrain_map_html(df, metric="speed", basemap="Satellite", exaggeration=1.5, height=700):
    fc, coords, info, label, (lo, hi), cmap = _prepare(df, metric)
    tiles, attrib, maxzoom = BASEMAPS[basemap]
    lons, lats = [c[0] for c in coords], [c[1] for c in coords]
    repl = {
        "__H__": str(height),
        "__BAR__": ", ".join(pc.sample_colorscale(cmap, list(np.linspace(0, 1, 8)))),
        "__LABEL__": label, "__LO__": f"{lo:.1f}", "__HI__": f"{hi:.1f}",
        "__ROUTE__": json.dumps(coords), "__TRACK__": json.dumps(fc), "__INFO__": json.dumps(info),
        "__BOUNDS__": json.dumps([[min(lons), min(lats)], [max(lons), max(lats)]]),
        "__TILES__": tiles, "__MAXZ__": str(maxzoom), "__ATTRIB__": attrib,
        "__EXAG__": str(exaggeration),
    }
    html = TEMPLATE
    for k, v in repl.items():
        html = html.replace(k, v)
    return html
