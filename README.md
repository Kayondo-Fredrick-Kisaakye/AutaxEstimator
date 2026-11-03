# AutaxEstimator

Server-rendered Uganda vehicle import tax estimator. The application uses Flask,
PostgreSQL, and local CSS. It does not require JavaScript.

## Local setup

```bash
source .venv/bin/activate
psql -h localhost -U autax_user -d autax_estimator -f config/schema.sql
export DATABASE_URL='postgresql://autax_user:YOUR_PASSWORD@localhost:5432/autax_estimator'
export SECRET_KEY='a-long-random-secret'
export DEFAULT_USD_TO_UGX_RATE='3700'
python -m app.web_server
```

Open `http://127.0.0.1:5000` after starting the server.

## Currency sync

Configure an approved provider endpoint that returns either `{"rate": 3700}`
or `{"rates": {"UGX": 3700}}`, then run:

```bash
export CURRENCY_API_URL='https://provider.example/latest?base=USD&symbols=UGX'
python -m app.currency_sync
```

The rate is cached in PostgreSQL with its source and UTC timestamp. The
estimator uses the newest cached rate and falls back to the manually supplied
rate when no cached rate exists.

## Vehicle data sync

Only use a source that permits automated access. Configure a JSON or CSV feed
with the fields `make`, `model`, `engine_cc`, `year_of_manufacture`, and
`cif_value_usd`:

```bash
export VEHICLE_DATA_URL='https://provider.example/vehicles.json'
export VEHICLE_DATA_FORMAT='json'
python -m app.scraper
```

The importer currently validates records but does not publish them to the
database automatically. Review and approve source data before adding an
importer for `makes`, `models`, and `valuations`.

## Production

Set `COOKIE_SECURE=1` behind HTTPS and run:

```bash
gunicorn -c gunicorn.conf.py app.web_server:app
```

The deployment health endpoint is `GET /health`. It returns HTTP 200 only when
the application can reach PostgreSQL.

Tax rates are stored in `tax_rules` so an authorized operator can update them
with an effective date and source. Confirm every rate with current official
URA guidance before using this for a real customs assessment.