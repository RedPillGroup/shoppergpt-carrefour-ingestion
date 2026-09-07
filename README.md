# shopper-gpt-carrefour-ingest

ETL pipeline that ingests the Carrefour Traiteur exports into MongoDB and Pinecone,
for the ShopperGPT assistant (`waib-api`).

## Principle

Stay as close as possible to Carrefour's raw data. The full source record is kept
under `raw` on every product, and the assistant reads it directly. We derive only
what the engine cannot infer at runtime — and we never invent a value: a missing
portion count stays missing rather than becoming an estimate, because a number the
LLM can multiply is a number it will trust.

Reads 3 JSONL exports from Carrefour (pulled from Google Cloud Storage — see
[Fetching the exports](#fetching-the-exports-gcs)) and upserts them into 3
MongoDB collections:

| GCS folder | Local file (`data/`) | Collection | Description |
|---|---|---|---|
| `catalogue/` | `catalogue_products_<date>.jsonl.gz` | `products` | Normalised product catalogue |
| `mapping/` | `mapping_products_prices_<date>.jsonl.gz` | `prices` | Per-store pricing matrix |
| `magasins/` | `magasins_stores_<date>.jsonl.gz` | `stores` | Store reference data |

To use `--fetch` (pull the latest exports from GCS), also authenticate with
Application Default Credentials:

```bash
gcloud auth application-default login
# or: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Setup

```bash
cp .env.example .env      # MONGO_URI, MONGO_DB, GEMINI_API_KEY, OPENAI_API_KEY, PINECONE_API_KEY
poetry install
```

## Run

```bash
# Fetch the latest exports from GCS, then ingest everything
poetry run python run.py --fetch

# Ingest everything from whatever is already in data/
poetry run python run.py

# Or one collection at a time (prepend --fetch to refresh from GCS first)
poetry run python run.py --stores
poetry run python run.py --prices
poetry run python run.py --products --force-categorize
poetry run python run.py --pinecone --reset-pinecone
```

`--fetch` composes with any of the above: it downloads first, then runs the
selected steps (or everything, when no step flag is given).

| Command | What it does |
|---|---|
| `run.py --stores` | `stores` collection (+ geo, delivery modes, curated concepts) |
| `run.py --prices` | `prices` collection — one row per (product, store) that has a price |
| `run.py --products` | `products` collection, including the LLM classifications |
| `run.py --catalogue` | per-store availability summaries; **needs `--products` + `--prices` first** |
| `run.py --pinecone` | embeds product names and upserts the vectors |
| `--force-categorize` | ignores the classification cache and re-asks the model |
| `--reset-pinecone` | wipes all vectors before re-ingesting (drops stale ones) |

## Fetching the exports (GCS)

Carrefour drops one dated export per stream into
`gs://carrefour-shoppergpt-ingestion/<folder>/` (`catalogue`, `magasins`,
`mapping`). `run.py --fetch` (see `ingest/fetch.py`) downloads the most recently
updated object of each into `data/`, names it `<local_prefix>_<date>.jsonl.gz`,
and removes that stream's previous local files so the newest export is always the
one ingested.

Bucket and project default to the current setup and can be overridden with
`GCS_BUCKET` / `GCS_PROJECT` (see `.env.example`). Auth uses Application Default
Credentials — see [Setup](#setup).

## Store concepts (manual CSV — NOT from GCS)

> **Don't skip this.** Missing this file silently breaks store-rayon logic in
> production.

The per-store **rayons / concepts** (Boucherie, Charcuterie & Traiteur, Pâtisserie…)
come from a **static** CSV that is **not** part of the daily GCS export and is
**not** pulled by `--fetch`. You must place it in `data/` yourself, with this
**exact** filename (the accent and spaces matter — `load_store_concepts` matches it
byte-for-byte):

```
data/Evénement X Concept - Concept X Magasin.csv
```

- **Source:** the Carrefour shared Drive. The `Evénement X Concept` workbook exports
  several tabs; **only the `Concept X Magasin` tab is used at runtime.** The sibling
  tabs (`Concept X Produits`, `Evénement X Concept`) are ignored — you can leave
  them out, or drop them in `data/` too, they're harmless.
- **Expected columns:** `ID Magasin`, `Nom Magasin`, `Statut` (`Activé` / `Désactivé`),
  then one column per concept holding a `1` / `0` flag. Read by
  `ingest/concepts.py:load_store_concepts`, written onto each store as
  `curated_concepts` during the **`--stores`** step.
- **If the file is missing,** every store gets an empty `curated_concepts`, and the
  assistant wrongly tells users a store lacks rayons it actually has (e.g. *"ce
  magasin ne dispose pas du rayon pâtisserie"*) and can block on it. This has
  already bitten us on the preprod bot.

After adding or updating the file, re-run the stores step (no `--fetch` needed —
this CSV is local, only the JSONL exports come from GCS):

```bash
poetry run python run.py --stores
```

## Data files

`--fetch` populates `data/` (gitignored) automatically. To run without GCS, drop
the exports there yourself — the pipeline picks the newest file matching each
prefix, `.jsonl` or `.jsonl.gz`:

```
data/
├── catalogue_products_<date>.jsonl.gz
├── mapping_products_prices_<date>.jsonl.gz
├── magasins_stores_<date>.jsonl.gz
└── Evénement X Concept - Concept X Magasin.csv   # manual — see "Store concepts" above
```

Legacy plain names (`products.jsonl`, `products_prices.jsonl`, `stores.jsonl`)
are still recognised as a fallback.

## Deployment (daily job on GKE)

Runs daily as a Kubernetes **CronJob** on GKE, mirroring `waib-rrg-jobs`. On push:
`develop` → dev cluster (`waib-dev`), `main` → prod (`waib-prod`). Each workflow
builds the image, pushes it to Artifact Registry, writes the secret from a GitHub
secret, and `kubectl apply`s `k8s/`.

Layout:
- `Dockerfile` — builds the image and **bakes in the concept CSV** (`data/Evénement X
  Concept - Concept X Magasin.csv`), since it isn't part of the GCS export.
- `k8s/cron.yaml` / `k8s/cronProd.yaml` — the CronJob (schedule `0 3 * * *` —
  03:00 UTC / 05:00 Paris, off-peak; runs `run.py --fetch`).
- `k8s/secret.yaml` — env vars; its `data` is overwritten at deploy from the
  `DEV_SECRETS` / `PROD_SECRETS` GitHub secret.
- `.github/workflows/{dev,prod}.yml` — CI.

**GitHub secrets** (per environment): `GCP_CREDENTIALS`, `GKE_PROJECT`, and
`DEV_SECRETS` / `PROD_SECRETS` — a YAML map containing at least `MONGO_URI`, `ENV`,
`GCS_BUCKET`, `GCS_PROJECT`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY`
(see `k8s/secret.yaml`).

**GCS access (Workload Identity).** `run.py --fetch` reads
`gs://carrefour-shoppergpt-ingestion`. `waib-dev` has **Workload Identity enabled**,
so the node default SA is not usable — the pod must run under a KSA bound to a GSA.
Bind the KSA `carrefour-ingestion` (namespace `default`) to the GSA
`carrefour-ingestion-sa`:

```bash
# 1. KSA + annotation (you can run these):
kubectl create serviceaccount carrefour-ingestion -n default
kubectl annotate serviceaccount carrefour-ingestion -n default \
  iam.gke.io/gcp-service-account=carrefour-ingestion-sa@waib-459906.iam.gserviceaccount.com

# 2. IAM (needs project admin — devops):
gcloud iam service-accounts add-iam-policy-binding \
  carrefour-ingestion-sa@waib-459906.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:waib-459906.svc.id.goog[default/carrefour-ingestion]"
gcloud storage buckets add-iam-policy-binding gs://carrefour-shoppergpt-ingestion \
  --member "serviceAccount:carrefour-ingestion-sa@waib-459906.iam.gserviceaccount.com" \
  --role roles/storage.objectViewer
```

The CronJob sets `serviceAccountName: carrefour-ingestion` (see `k8s/cron.yaml`).

**Schedule.** Runs daily at **`0 3 * * *` = 03:00 UTC (05:00 Europe/Paris)** —
deep off-peak, so a full ingest never competes with live traffic (midday is a
usage peak). Kubernetes cron is **UTC** by default; to pin it to local time
instead, add `timeZone: "Europe/Paris"` next to `schedule` (GKE ≥ 1.27).

The slot deliberately does **not** try to line up with Carrefour's export: its
publish time is variable and unconfirmed. `--fetch` always pulls the latest
object and the skip logic (`ingestion_meta` marker in Mongo) ingests only when a
genuinely new file has landed — so an export published after a run is simply
picked up on the **next** run (at most ~1 day of lag, fine for slow-moving
catalogue data). To change the cadence, edit `schedule` in **both** `k8s/cron.yaml`
and `k8s/cronProd.yaml`, then redeploy.

One-time prereq: the Artifact Registry repo `shoppergpt-carrefour-ingestion`. The
CronJob `resources` are placeholders — tune after the first real run.

## What gets derived

Everything else on the document is raw Carrefour data, unmodified.

| Field | Source | Notes |
|---|---|---|
| `menu_step` | Gemini | Apéritifs, Entrées, Plats, Sauces, Fromages, Desserts, Boissons, Pains, Petit Déj, Table & Déco. Must stay in sync with `MENU_STEPS_ORDERED` in the API's `engine.py`. |
| `dish_role` | Gemini | `main` / `side`, on Plats only — the step mixes a roast with its gratin, and the engine needs one protein main. |
| `drink_role` | Gemini | `eau, soft, vin, petillant, champagne, biere, cidre, spiritueux, aperitif, chaud` — selects which per-guest proportion rule applies. Boissons only. |
| `could_fit_event` | Gemini | Occasions the product genuinely suits, or `["ALL"]`. Mirrors `EVENT_CATEGORIES` in the API. |
| `volume_ml` | `raw.weight` | Bottle volume, Boissons only. The raw field is a decimal *string*, and on food it is a mass in grams — hence the guard, plus a 200 ml plausibility floor (a 34 g box of tea bags lives in the same field). |
| `dietary_tags` | `raw.type_envie` | The diet subset of Carrefour's own tags (`sans porc`, `sans viande`, `sans poisson`, `végétarien`) isolated from the sensory ones, for the composer and the dietary critic. A strict whitelist — never inferred. |
| `persons` | `raw.nb_portion` | `None` when Carrefour gives nothing. No fallback. |
| `price_ref` | `prices` | Median across stores, used only when no store is selected — the store's own price always wins. |
| `is_composable` / `composition_plateau` | `raw.composition_plateau` | Genuine build-your-own products, from Carrefour's structured groups (never name keywords). Piece `code`s are kept: the cart API needs them verbatim. |
| `recommendable` | product name | `False` only for "au choix / à composer" products with no structured data behind them. Excluded from Mongo and Pinecone unless `INGEST_NON_RECOMMENDABLE=true`. |
| `delai_prepa` | raw | Global lead time in days; per-store overrides stay in `raw.carrefour_delay`. |

On stores, `--catalogue` adds `step_catalogue` (product count per step),
`step_families` (which sub-families the store actually carries — grounds the API's
query planner) and `step_typical_cost` (median €/guest per step).

### The classification cache

Each Gemini classification is written with a `<field>_source: "llm"` marker and
reused on every later ingest, so a product is classified once. The cache is keyed
on `product_id` alone: if Carrefour ever renames a product in place, its old
classifications persist. Measured at zero drift over the June→August exports
(1343 products, no name change); `--force-categorize` is the remedy if it happens.

## Pinecone

The embedded text is the **product name only** — ingredients and keywords dilute
the vector. Metadata is `menu_step` + `status`, the only two things the API filters
on. Index: `waib-carrefour-dev-large` / `waib-carrefour-prod-large` (1536 dims).

## Tests

```bash
poetry run pytest
```

Pure-function tests only — no MongoDB, no network. They cover what decides the
data: the derivations, the document shape, and the drink-family overrides.

## Maintenance scripts

```bash
poetry run python scripts/missing_portions.py       # products with no nb_portion, for Carrefour
poetry run python scripts/drop_fossil_fields.py     # dry-run; --apply to unset dead fields
poetry run python scripts/reclassify_stale_steps.py # dry-run; --apply to re-ask on removed steps
```
