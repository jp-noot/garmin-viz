"""Tableau de bord : streamlit run app.py"""
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from garmin_viz import plots, stats
from garmin_viz.terrain import terrain_map_html
from garmin_viz.loader import list_activities, load_activity
from garmin_viz.vo2max import load_vo2max

STATIC = Path(__file__).parent / "static"
STATIC.mkdir(exist_ok=True)

st.set_page_config(page_title="Garmin Viz", layout="wide")
st.title("Mes activités Garmin")

folder = st.sidebar.text_input("Dossier des activités (.fit / .gpx)", "data/activities")
hr_max = st.sidebar.number_input("FC max", 120, 230, 190)
metric = st.sidebar.selectbox("Couleur de la trace", list(plots.METRICS), format_func=lambda m: plots.METRICS[m][0])
basemap = st.sidebar.selectbox("Fond de carte", ["Satellite", "Plan OSM", "Topo"])
relief = st.sidebar.slider("Relief du terrain", 1.0, 3.0, 1.5, 0.1)
exag = st.sidebar.slider("Exagération du relief", 1.0, 10.0, 3.0)

files = list_activities(folder)
if not files:
    st.info(f"Aucun fichier .fit/.gpx dans « {folder} ». Copie tes activités dedans.")
    st.stop()



@st.cache_data
def get(p, _mtime=0):
    return load_activity(p)


@st.cache_data
def build_history(paths_mtimes):
    rows = []
    for p, m in paths_mtimes:
        try:
            rows.append(stats.history_row(get(p, m), Path(p).name))
        except Exception:  # fichier FIT sans activité (réglages, suivi quotidien...)
            continue
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True) if rows else pd.DataFrame()


hist = build_history(tuple((str(p), p.stat().st_mtime) for p in files))
if hist.empty:
    st.info("Aucune activité exploitable (avec points GPS/temps) dans ce dossier.")
    st.stop()

by_name = {p.name: p for p in files}
ordered = hist.sort_values("date", ascending=False)
labels = {r.fichier: f"{r.date:%d/%m/%Y %H:%M} · {r.distance_km:g} km · {stats.pace_label(r.allure_min_km)}/km"
          for r in ordered.itertuples()}
names = list(ordered.fichier)
if st.session_state.get("act") not in names:
    st.session_state["act"] = names[0]  # la plus récente par défaut


def pick_from_table():
    """Clic sur une ligne de l'historique -> sélectionne cette sortie."""
    rows = st.session_state["hist_table"]["selection"]["rows"]
    if rows:
        st.session_state["act"] = st.session_state["hist_names"][rows[0]]


name = st.selectbox("Sortie affichée dans les onglets Carte, Trace et Statistiques",
                    names, format_func=labels.get, key="act")
path = by_name[name]

df = get(str(path), path.stat().st_mtime)
tabhist, tabmap, tab3d, tabstats, tabvo2 = st.tabs(["Historique", "Carte relief 3D", "Trace 3D", "Statistiques", "VO2max"])

with tabhist:
    h = hist
    a, b, c, d = st.columns(4)
    a.metric("Sorties", len(h))
    b.metric("Distance totale", f"{h.distance_km.sum():.1f} km")
    c.metric("Temps total", f"{int(h.duree_min.sum() // 60)}h{int(h.duree_min.sum() % 60):02d}")
    d.metric("Allure moyenne", stats.pace_label(h.allure_min_km.mean()) + " /km")
    if len(h) > 1:
        c1, c2 = st.columns(2)
        c1.plotly_chart(plots.history_distance(h), width="stretch")
        c2.plotly_chart(plots.history_pace(h), width="stretch")
        c3, c4 = st.columns(2)
        c3.plotly_chart(plots.history_hr(h), width="stretch")
        c4.plotly_chart(plots.history_weekly(h), width="stretch")
    st.subheader("Toutes mes sorties")
    table = h.sort_values("date", ascending=False).assign(allure=lambda x: x.allure_min_km.map(stats.pace_label))
    st.session_state["hist_names"] = list(table.fichier)
    st.caption("Clique sur une ligne pour afficher cette sortie sur la carte 3D, la trace et les statistiques.")
    st.dataframe(
        table[["date", "distance_km", "duree_min", "allure", "vitesse_kmh", "fc_moy", "fc_max", "denivele_pos_m"]],
        hide_index=True, width="stretch", key="hist_table", on_select=pick_from_table,
        selection_mode="single-row",
        column_config={
            "date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY HH:mm"),
            "distance_km": "Distance (km)", "duree_min": "Durée (min)", "allure": "Allure (/km)",
            "vitesse_kmh": "Vitesse (km/h)", "fc_moy": "FC moy", "fc_max": "FC max", "denivele_pos_m": "D+ (m)"})
    if st.checkbox("Afficher toutes les sorties sur une carte"):
        tracks = [(f"{r.date:%d/%m %H:%M} · {r.distance_km:g} km", get(str(by_name[r.fichier]), by_name[r.fichier].stat().st_mtime))
                  for r in h.sort_values("date").itertuples()]
        st.plotly_chart(plots.all_tracks_map(tracks), width="stretch")

with tabmap:
    st.markdown(f"**Sortie : {labels[name]}**")
    if df["lat"].notna().any():
        html = terrain_map_html(df, metric, basemap, relief)
        # La carte est servie comme une vraie page (URL propre) plutôt qu'en iframe "srcdoc" :
        # certains navigateurs (Firefox) y bloquent les Web Workers de MapLibre -> pas de tracé.
        key = hashlib.md5(html.encode()).hexdigest()[:10]
        page = STATIC / f"carte_{key}.html"
        if not page.exists():
            for old in STATIC.glob("carte_*.html"):  # nettoie les anciennes cartes
                old.unlink(missing_ok=True)
            page.write_text(html, encoding="utf-8")
        url = f"/app/static/{page.name}"
        st.iframe(url, height=720)
        c1, c2 = st.columns(2)
        c1.link_button("Ouvrir dans un onglet", url)
        c2.download_button("Télécharger la carte (HTML autonome)", html,
                           file_name=f"{path.stem}_carte.html", mime="text/html")
        st.caption("Clic droit + glisser (ou Ctrl + glisser) pour pivoter / incliner. Molette pour zoomer.")
    else:
        st.warning("Pas de GPS dans cette activité (indoor ?).")

with tab3d:
    st.markdown(f"**Sortie : {labels[name]}**")
    if df["lat"].notna().any():
        st.plotly_chart(plots.track_3d(df, metric, exag), width="stretch")
    else:
        st.warning("Pas de GPS dans cette activité (indoor ?).")

with tabstats:
    st.markdown(f"**Sortie : {labels[name]}**")
    s = stats.summary(df)
    cols = st.columns(4)
    for i, (k, v) in enumerate(s.items()):
        cols[i % 4].metric(k, v if v is not None else "-")
    st.plotly_chart(plots.timeseries(df), width="stretch")
    if df["hr"].notna().any():
        st.plotly_chart(plots.zones_bar(stats.hr_zones(df, hr_max)), width="stretch")
    if df["distance"].notna().any():
        st.subheader("Allure par km")
        st.dataframe(stats.km_splits(df), hide_index=True)

with tabvo2:
    export = st.text_input("Dossier de l'export Garmin (zip décompressé)", "data")
    v = load_vo2max(export)
    if v.empty:
        st.info("Aucune donnée VO2max trouvée (cherche MetricsMaxMetData*.json dans l'export).")
    else:
        st.plotly_chart(plots.vo2_line(v), width="stretch")
