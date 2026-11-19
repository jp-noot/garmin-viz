# garmin-viz

Tableau de bord perso pour les données Garmin : historique des sorties, carte **relief 3D**
avec survol animé (flèche + trait parcouru + compteur en direct), statistiques (vitesse, FC, zones,
allure par km) et évolution du **VO2max**.

## Installation
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Récupérer ses données
- **Synchro automatique** (API non officielle `garminconnect`) :
  1ère fois dans un vrai terminal : `python download.py --email TON_MAIL` (mot de passe + MFA),
  puis simplement `python download.py` (jeton enregistré dans `~/.garminconnect`).
  Télécharge les nouvelles activités dans `data/activities/` et l'historique VO2max.
- **Export complet** Garmin (garmin.com/account/datamanagement) : décompresser dans `data/`,
  puis `python extract_export.py` pour extraire les `.fit`. Évite de mélanger avec la synchro (doublons).
- **USB** : copier `GARMIN/Activity/*.fit` dans `data/activities/`. Les `.gpx` sont lus aussi.

## Lancer
    ./lancer.sh        # synchronise, démarre l'appli et ouvre le navigateur
    ./arreter.sh       # arrête l'appli
ou `streamlit run app.py`. Une icône de lancement (`.desktop`) peut pointer sur `lancer.sh`.

## Organisation
- `garmin_viz/loader.py` : lecture FIT/GPX -> DataFrame
- `garmin_viz/stats.py`, `plots.py`, `vo2max.py` : calculs et graphiques
- `garmin_viz/terrain.py` : carte 3D MapLibre (relief AWS, fonds Esri/OSM/OpenTopoMap)
- `app.py` : interface Streamlit

## Confidentialité
`data/` (traces GPS, export Garmin), les cartes générées et les fichiers `.fit/.gpx` sont exclus de git.
Ne jamais committer de données issues de l'export.

## Licence
MIT, voir [LICENSE](LICENSE).
