"""Lecture des activités Garmin (FIT et GPX) vers un DataFrame unifié.

Colonnes : time, lat, lon, alt, hr, speed (m/s), cadence, temp, distance (m)
"""
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

SEMICIRCLE = 180 / 2**31
COLUMNS = ["time", "lat", "lon", "alt", "hr", "speed", "cadence", "temp", "distance"]


def load_fit(path) -> pd.DataFrame:
    import fitdecode

    rows = []
    with fitdecode.FitReader(str(path)) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record":
                d = {f.name: f.value for f in frame.fields}
                lat, lon = d.get("position_lat"), d.get("position_long")
                rows.append({
                    "time": d.get("timestamp"),
                    "lat": lat * SEMICIRCLE if lat is not None else None,
                    "lon": lon * SEMICIRCLE if lon is not None else None,
                    "alt": d.get("enhanced_altitude", d.get("altitude")),
                    "hr": d.get("heart_rate"),
                    "speed": d.get("enhanced_speed", d.get("speed")),
                    "cadence": d.get("cadence"),
                    "temp": d.get("temperature"),
                    "distance": d.get("distance"),
                })
    return _finalize(pd.DataFrame(rows, columns=COLUMNS))


def load_gpx(path) -> pd.DataFrame:
    """GPX avec extensions Garmin (gpxtpx:hr, cad, atemp) si présentes."""
    rows = []
    for _, el in ET.iterparse(str(path)):
        if el.tag.rsplit("}", 1)[-1] != "trkpt":
            continue
        d = {"lat": float(el.get("lat")), "lon": float(el.get("lon"))}
        for sub in el.iter():
            name = sub.tag.rsplit("}", 1)[-1]
            txt = (sub.text or "").strip()
            if not txt:
                continue
            if name == "ele":
                d["alt"] = float(txt)
            elif name == "time":
                d["time"] = txt
            elif name == "hr":
                d["hr"] = float(txt)
            elif name == "cad":
                d["cadence"] = float(txt)
            elif name == "atemp":
                d["temp"] = float(txt)
        rows.append(d)
        el.clear()
    df = pd.DataFrame(rows)
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    return _finalize(df[COLUMNS])


def _haversine(lat, lon):
    lat, lon = np.radians(lat.to_numpy(float)), np.radians(lon.to_numpy(float))
    dlat, dlon = np.diff(lat), np.diff(lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    return 2 * 6371000 * np.arcsin(np.sqrt(a))


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for c in COLUMNS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    # distance et vitesse recalculées depuis le GPS si absentes (cas du GPX)
    if df["distance"].isna().all() and df["lat"].notna().sum() > 1:
        g = df.dropna(subset=["lat", "lon"])
        seg = _haversine(g["lat"], g["lon"])
        df.loc[g.index, "distance"] = np.concatenate([[0], np.cumsum(seg)])
        df["distance"] = df["distance"].ffill()
    if df["speed"].isna().all() and df["distance"].notna().any():
        dt = df["time"].diff().dt.total_seconds()
        df["speed"] = (df["distance"].diff() / dt).rolling(5, min_periods=1, center=True).mean()
    return df


def load_activity(path) -> pd.DataFrame:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".fit":
        return load_fit(path)
    if ext == ".gpx":
        return load_gpx(path)
    raise ValueError(f"Format non supporté : {ext}")


def list_activities(folder) -> list[Path]:
    folder = Path(folder)
    files = [p for p in folder.rglob("*") if p.suffix.lower() in (".fit", ".gpx")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
