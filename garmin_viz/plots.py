"""Graphiques Plotly."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

METRICS = {
    "speed": ("Vitesse (km/h)", 3.6, "Turbo"),
    "hr": ("FC (bpm)", 1, "Reds"),
    "alt": ("Altitude (m)", 1, "Viridis"),
    "cadence": ("Cadence", 1, "Blues"),
}


def track_3d(df, metric="speed", vertical_exag=3.0):
    """Trace 3D : x=lon, y=lat (en mètres locaux), z=altitude, couleur=metric."""
    g = df.dropna(subset=["lat", "lon", "alt"])
    label, k, cmap = METRICS[metric]
    lat0 = g["lat"].mean()
    x = (g["lon"] - g["lon"].mean()) * 111320 * np.cos(np.radians(lat0))
    y = (g["lat"] - lat0) * 110540
    z = g["alt"] * vertical_exag
    c = g[metric] * k
    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=x, y=y, z=z, mode="markers",
        marker=dict(size=3, color=c, colorscale=cmap, colorbar=dict(title=label)),
        text=[f"{label}: {v:.1f}<br>alt: {a:.0f} m" for v, a in zip(c, g["alt"])],
        hoverinfo="text", name="trace",
    ))
    # ombre au sol pour lire le relief
    fig.add_trace(go.Scatter3d(x=x, y=y, z=np.full(len(z), z.min()), mode="lines",
                               line=dict(color="gray", width=2), hoverinfo="skip", name="projection"))
    fig.update_layout(
        scene=dict(xaxis_title="Est-Ouest (m)", yaxis_title="Nord-Sud (m)",
                   zaxis_title=f"Altitude (x{vertical_exag:g})", aspectmode="data"),
        margin=dict(l=0, r=0, t=30, b=0), height=650, showlegend=False,
    )
    return fig


def map_2d(df, metric="speed"):
    g = df.dropna(subset=["lat", "lon"])
    label, k, cmap = METRICS[metric]
    fig = px.scatter_map(g, lat="lat", lon="lon", color=g[metric] * k,
                         color_continuous_scale=cmap, zoom=12, height=500,
                         labels={"color": label})
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    return fig


def timeseries(df):
    x = df["distance"] / 1000 if df["distance"].notna().any() else df["time"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("Vitesse (km/h)", "Fréquence cardiaque (bpm)", "Altitude (m)"))
    fig.add_trace(go.Scatter(x=x, y=df["speed"].rolling(10, min_periods=1).mean() * 3.6, name="vitesse"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=df["hr"], name="FC", line=dict(color="crimson")), 2, 1)
    fig.add_trace(go.Scatter(x=x, y=df["alt"], name="altitude", fill="tozeroy",
                             line=dict(color="seagreen")), 3, 1)
    fig.update_xaxes(title_text="Distance (km)" if df["distance"].notna().any() else "Temps", row=3, col=1)
    fig.update_layout(height=650, showlegend=False, margin=dict(t=40))
    return fig


def zones_bar(zdf):
    return px.bar(zdf, x="zone", y="minutes", color="zone", height=350,
                  title="Temps par zone de FC (min)").update_layout(showlegend=False)


def vo2_line(vdf):
    return px.line(vdf, x="date", y="vo2max", color="sport", markers=True,
                   title="Évolution du VO2max", height=400)


def _hover_pace(h):
    from .stats import pace_label
    return [pace_label(m) + " /km" for m in h["allure_min_km"]]


def history_distance(h):
    fig = px.bar(h, x="date", y="distance_km", text="distance_km", height=320,
                 labels={"date": "", "distance_km": "Distance (km)"}, title="Distance par sortie")
    fig.update_traces(textposition="outside", marker_color="#2a9d8f")
    return fig


def history_pace(h):
    fig = go.Figure(go.Scatter(x=h["date"], y=h["allure_min_km"], mode="lines+markers",
                               text=_hover_pace(h), hovertemplate="%{x|%d/%m/%Y}<br>%{text}<extra></extra>",
                               line=dict(color="#e76f51")))
    fig.update_yaxes(autorange="reversed", title="Allure (min/km, plus bas = plus rapide)")
    fig.update_layout(height=320, title="Allure moyenne", margin=dict(t=50))
    return fig


def history_hr(h):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h["date"], y=h["fc_moy"], mode="lines+markers", name="FC moy",
                             line=dict(color="crimson")))
    fig.add_trace(go.Scatter(x=h["date"], y=h["fc_max"], mode="lines+markers", name="FC max",
                             line=dict(color="#999", dash="dot")))
    fig.update_layout(height=320, title="Fréquence cardiaque", yaxis_title="bpm", margin=dict(t=50))
    return fig


def history_weekly(h):
    w = (h.set_index("date")["distance_km"].resample("W-MON", label="left", closed="left").sum()
         .reset_index().rename(columns={"distance_km": "km"}))
    fig = px.bar(w, x="date", y="km", height=320, title="Kilomètres par semaine",
                 labels={"date": "Semaine du", "km": "km"})
    fig.update_traces(marker_color="#264653")
    return fig


def all_tracks_map(tracks):
    """tracks : liste de (libellé, DataFrame) -> toutes les sorties sur une même carte."""
    fig = go.Figure()
    palette = px.colors.qualitative.Bold
    lats, lons = [], []
    for i, (label, df) in enumerate(tracks):
        g = df.dropna(subset=["lat", "lon"])
        if len(g) > 400:
            g = g.iloc[np.linspace(0, len(g) - 1, 400).astype(int)]
        if g.empty:
            continue
        lats += [g.lat.min(), g.lat.max()]
        lons += [g.lon.min(), g.lon.max()]
        fig.add_trace(go.Scattermap(lat=g.lat, lon=g.lon, mode="lines", name=label,
                                    line=dict(width=4, color=palette[i % len(palette)])))
    if lats:
        fig.update_layout(map=dict(style="open-street-map",
                                   center=dict(lat=float(np.mean(lats)), lon=float(np.mean(lons))), zoom=11))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), legend=dict(bgcolor="rgba(255,255,255,0.8)"))
    return fig
