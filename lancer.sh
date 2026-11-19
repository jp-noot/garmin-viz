#!/usr/bin/env bash
# Synchronise les nouvelles activités Garmin, puis ouvre le tableau de bord.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PORT=8501
URL="http://localhost:$PORT"

echo "== Synchronisation Garmin Connect =="
if ! .venv/bin/python download.py; then
    echo
    echo "La synchro a échoué (voir message ci-dessus). Le tableau de bord s'ouvre quand même"
    echo "avec les activités déjà téléchargées."
fi

echo
echo "== Tableau de bord =="
if curl -s -o /dev/null "$URL"; then
    echo "Déjà lancé."
else
    setsid nohup .venv/bin/streamlit run app.py --server.headless true --server.port "$PORT" \
        --browser.gatherUsageStats false >/tmp/garmin-viz.log 2>&1 &
    for _ in $(seq 1 30); do curl -s -o /dev/null "$URL" && break; sleep 0.5; done
fi
[ -z "$NO_BROWSER" ] && xdg-open "$URL" >/dev/null 2>&1
echo "Ouvert : $URL   (arrêt : ./arreter.sh)"
sleep 3
