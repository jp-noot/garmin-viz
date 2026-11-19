"""Extraction du VO2max depuis l'export complet Garmin (fichiers JSON).

Dans l'export : DI_CONNECT/DI-Connect-Metrics/MetricsMaxMetData_*.json
(la structure varie selon les versions : on cherche donc les clés de façon tolérante).
"""
import json
from pathlib import Path
import pandas as pd


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def load_vo2max(export_folder) -> pd.DataFrame:
    rows = []
    for f in Path(export_folder).rglob("MetricsMaxMetData*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for d in _walk(data):
            precise = d.get("vo2MaxPreciseValue")  # fourni par l'API (ex. 46.3), absent de l'export (46)
            val = precise or d.get("vo2MaxValue") or d.get("vo2Max")
            date = d.get("calendarDate") or d.get("updateTimestamp") or d.get("date")
            if val and date:
                rows.append({"date": date, "vo2max": float(val),
                             "sport": d.get("sport") or "RUNNING", "precise": bool(precise)})
    if not rows:
        return pd.DataFrame(columns=["date", "vo2max", "sport"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["date"]).sort_values("precise", ascending=False)  # préfère la valeur précise
    df["date"] = df["date"].dt.normalize()
    return (df.drop_duplicates(["date", "sport"]).drop(columns="precise")
              .sort_values("date").reset_index(drop=True))
