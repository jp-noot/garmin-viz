#!/usr/bin/env bash
# Arrête le tableau de bord.
pkill -f "streamlit run app.py" && echo "Arrêté." || echo "Rien à arrêter."
