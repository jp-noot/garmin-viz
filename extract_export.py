"""Extrait les .fit de l'export Garmin vers data/activities (en renommant proprement).

    python extract_export.py [dossier_export] [dossier_sortie]
"""
import re
import sys
import zipfile
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/DI_CONNECT/DI-Connect-Uploaded-Files")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "data/activities")
out.mkdir(parents=True, exist_ok=True)

n = 0
for z in sorted(src.glob("*.zip")):
    with zipfile.ZipFile(z) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".fit"):
                continue
            # retire l'adresse mail du nom de fichier : garde l'id numérique
            m = re.search(r"(\d+)\.fit$", name, re.I)
            target = out / f"{m.group(1) if m else Path(name).stem}.fit"
            if not target.exists():
                target.write_bytes(zf.read(name))
                n += 1
print(f"{n} fichiers extraits dans {out}")
