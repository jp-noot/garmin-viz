"""Télécharge les nouvelles activités Garmin Connect dans data/activities (API non officielle).

Première fois (interactif, saisit mot de passe + code MFA éventuel) :
    python download.py --email toi@mail.com

Ensuite, le jeton est réutilisé (stocké dans ~/.garminconnect) : plus rien à saisir.
    python download.py              # nouvelles activités uniquement
    python download.py --limit 200  # remonter plus loin dans l'historique
"""
import argparse
import getpass
import io
import json
import os
import zipfile
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

TOKENS = Path(os.environ.get("GARMIN_TOKENS", "~/.garminconnect")).expanduser()

ap = argparse.ArgumentParser()
ap.add_argument("--email", default=os.environ.get("GARMIN_EMAIL"))
ap.add_argument("--limit", type=int, default=30, help="nb d'activités récentes à vérifier")
ap.add_argument("--out", default="data/activities")
a = ap.parse_args()


def connect() -> Garmin:
    # 1) jeton déjà enregistré -> aucune saisie
    if TOKENS.exists():
        try:
            c = Garmin()
            c.login(str(TOKENS))
            return c
        except Exception as e:
            print(f"Jeton invalide ({e}), reconnexion...")
    # 2) connexion complète
    if not a.email:
        raise SystemExit("Première connexion : relance avec --email toi@mail.com")
    pwd = os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Mot de passe Garmin : ")
    c = Garmin(a.email, pwd, prompt_mfa=lambda: input("Code MFA : "))
    c.login(str(TOKENS))  # enregistre le jeton dans TOKENS
    TOKENS.chmod(0o700) if TOKENS.is_dir() else None
    return c


client = connect()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)

new = 0
for act in client.get_activities(0, a.limit):
    aid = str(act["activityId"])
    target = out / f"{aid}.fit"
    if target.exists():
        continue
    raw = client.download_activity(aid, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
    try:  # l'original arrive zippé
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            fit = next(z.read(n) for n in z.namelist() if n.lower().endswith(".fit"))
    except zipfile.BadZipFile:
        fit = raw
    target.write_bytes(fit)
    new += 1
    print("OK", act["startTimeLocal"][:16], act.get("activityName", ""), aid)
print(f"{new} nouvelle(s) activité(s).")

# VO2max : historique des 12 derniers mois (Garmin ne produit une valeur que les jours de course)
try:
    start = (date.today() - timedelta(days=365)).isoformat()
    m = client.get_max_metrics_range(start, date.today().isoformat())
    vdir = Path("data/DI_CONNECT/DI-Connect-Metrics")
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "MetricsMaxMetData_api.json").write_text(json.dumps(m))  # écrasé à chaque synchro
    n = len(m) if isinstance(m, list) else 0
    print(f"VO2max : {n} mesure(s) mise(s) à jour.")
except Exception as e:
    print("VO2max non récupéré :", e)
