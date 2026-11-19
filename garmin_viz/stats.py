"""Statistiques d'une activité."""
import numpy as np
import pandas as pd

ZONE_BOUNDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.01]  # fractions de la FC max
ZONE_NAMES = ["Z1 récup", "Z2 endurance", "Z3 tempo", "Z4 seuil", "Z5 max"]


def fmt_pace(speed_ms: float) -> str:
    if not speed_ms or speed_ms <= 0 or np.isnan(speed_ms):
        return "-"
    s = 1000 / speed_ms
    return f"{int(s // 60)}:{int(s % 60):02d} /km"


def _elevation(alt: pd.Series, threshold: float = 3.0):
    """D+/D- avec lissage et hysteresis (ignore les variations < threshold m)."""
    a = alt.rolling(15, min_periods=1, center=True).median().to_numpy()
    ref, gain, loss = a[0], 0.0, 0.0
    for v in a[1:]:
        if v - ref >= threshold:
            gain += v - ref
            ref = v
        elif ref - v >= threshold:
            loss += ref - v
            ref = v
    return gain, loss


def summary(df: pd.DataFrame) -> dict:
    dur = (df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds()
    dist = df["distance"].dropna().iloc[-1] if df["distance"].notna().any() else np.nan
    alt = df["alt"].dropna()
    gain, loss = _elevation(alt) if len(alt) > 1 else (np.nan, np.nan)
    return {
        "Date": df["time"].iloc[0].strftime("%Y-%m-%d %H:%M"),
        "Durée": f"{int(dur // 3600)}h{int(dur % 3600 // 60):02d}",
        "Distance (km)": round(float(dist) / 1000, 2) if dist == dist else None,
        "Vitesse moy (km/h)": round(float(df["speed"].mean()) * 3.6, 1),
        "Vitesse max (km/h)": round(float(df["speed"].max()) * 3.6, 1),
        "Allure moy": fmt_pace(df["speed"].mean()),
        "FC moy": round(df["hr"].mean()) if df["hr"].notna().any() else None,
        "FC max": int(df["hr"].max()) if df["hr"].notna().any() else None,
        "D+ (m)": round(gain) if gain == gain else None,
        "D- (m)": round(loss) if loss == loss else None,
        "Alt max (m)": round(alt.max()) if len(alt) else None,
    }


def hr_zones(df: pd.DataFrame, hr_max: float) -> pd.DataFrame:
    hr = df["hr"].dropna()
    dt = df["time"].diff().dt.total_seconds().clip(upper=10).reindex(hr.index).fillna(1)
    z = pd.cut(hr / hr_max, ZONE_BOUNDS, labels=ZONE_NAMES, right=False)
    out = (dt.groupby(z, observed=False).sum() / 60).rename("minutes")
    return pd.DataFrame({"zone": out.index.astype(str), "minutes": out.values.round(1)})


def km_splits(df: pd.DataFrame) -> pd.DataFrame:
    g = df.dropna(subset=["distance"]).copy()
    g["km"] = (g["distance"] // 1000).astype(int) + 1
    t = g.groupby("km").agg(
        t0=("time", "first"), t1=("time", "last"),
        hr=("hr", "mean"), d=("distance", lambda s: s.iloc[-1] - s.iloc[0]),
    )
    t["secondes"] = (t["t1"] - t["t0"]).dt.total_seconds()
    t["allure"] = [fmt_pace(d / s) if s else "-" for d, s in zip(t["d"], t["secondes"])]
    return t[["allure", "hr"]].round(0).reset_index()


def history_row(df: pd.DataFrame, name: str) -> dict:
    """Résumé numérique d'une activité (une ligne de l'historique)."""
    dur = (df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds()
    dist = df["distance"].dropna().iloc[-1] if df["distance"].notna().any() else np.nan
    alt = df["alt"].dropna()
    gain, _ = _elevation(alt) if len(alt) > 1 else (np.nan, np.nan)
    speed = dist / dur if dur and dist == dist else np.nan  # m/s moyen (pauses incluses)
    return {
        "fichier": name,
        "date": df["time"].iloc[0].tz_convert(None),
        "distance_km": round(float(dist) / 1000, 2) if dist == dist else np.nan,
        "duree_min": round(dur / 60, 1),
        "vitesse_kmh": round(float(speed) * 3.6, 2) if speed == speed else np.nan,
        "allure_min_km": round(1000 / speed / 60, 2) if speed == speed and speed > 0 else np.nan,
        "fc_moy": round(float(df["hr"].mean())) if df["hr"].notna().any() else np.nan,
        "fc_max": int(df["hr"].max()) if df["hr"].notna().any() else np.nan,
        "denivele_pos_m": round(gain) if gain == gain else np.nan,
    }


def pace_label(minutes: float) -> str:
    if minutes != minutes:
        return "-"
    return f"{int(minutes)}:{int(round((minutes % 1) * 60)):02d}"
