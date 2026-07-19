# Deploying to shinyapps.io (free)

Locally the app reads the live `ruuvi.db`. To publish a **shareable link**, deploy the
snapshot version to shinyapps.io (free tier: 5 apps, ~25 active hrs/month). The deployed
app has no database, so it automatically uses `data/garage_readings.csv`.

## One-time setup

1. Create a free account at <https://www.shinyapps.io>.
2. In the dashboard: **Account → Tokens → Show** — copy your **token** and **secret**.
3. Register the account locally (from the repo root):

   ```
   .venv/bin/rsconnect add --account <ACCOUNT> --name <ACCOUNT> --token <TOKEN> --secret <SECRET>
   ```

## Deploy / update

1. Refresh the snapshot so the deployed app has current data:

   ```
   python3 extract_data.py
   ```

2. Deploy:

   ```
   .venv/bin/rsconnect deploy shiny . --entrypoint app:app --title garage-print-window
   ```

`rsconnect` reads `requirements.txt` for dependencies. Re-run steps 1–2 to push updates.

## Run locally (live data)

```
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt
.venv/bin/shiny run app.py        # http://127.0.0.1:8000  (reads live ruuvi.db)
GARAGE_FORCE_CSV=1 .venv/bin/shiny run app.py   # force the snapshot source
```
