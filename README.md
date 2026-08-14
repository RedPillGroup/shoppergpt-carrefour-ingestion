# shopper-gpt-carrefour-ingest

ETL pipeline that ingests the Carrefour Traiteur JSONL exports into MongoDB.

## What it does

Reads 3 JSONL exports from Carrefour (pulled from Google Cloud Storage — see
[Fetching the exports](#fetching-the-exports-gcs)) and upserts them into 3
MongoDB collections:

| GCS folder | Local file (`data/`) | Collection | Description |
|---|---|---|---|
| `catalogue/` | `catalogue_products_<date>.jsonl.gz` | `products` | Normalised product catalogue |
| `mapping/` | `mapping_products_prices_<date>.jsonl.gz` | `prices` | Per-store pricing matrix |
| `magasins/` | `magasins_stores_<date>.jsonl.gz` | `stores` | Store reference data |

During ingestion, the pipeline derives the fields the AI recommendation engine needs:

- **`menu_step`** — course classification (Apéritifs / Entrées / Plats / Fromages / Desserts / Boissons), inferred from categories + department until Carrefour provides a dedicated field
- **`dietary_tags`** — dietary restrictions from `type_envie` (végétarien, sans porc, sans poisson…)
- **`persons`** — how many people one unit serves, from `nb_portion` → `weight` → estimate
- **`price_ref`** — median price across all stores, used by the LLM when no store context is set
- **`embed_text`** — clean concatenated text (name + ingredients + keywords + composition) ready for Pinecone embeddings later
- **`image_url`** — absolute CDN URL resolved from relative Magento paths

## Setup

```bash
cp .env.example .env
# fill in MONGO_URI and MONGO_DB
poetry install
```

To use `--fetch` (pull the latest exports from GCS), also authenticate with
Application Default Credentials:

```bash
gcloud auth application-default login
# or: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
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

## MongoDB collections

### `products`
```js
{
  _id: 31,                      // product_id (Magento)
  sku: "201602153",
  name: "Plateau entre amis",
  status: "active",             // "active" | "inactive"
  type_id: "simple",            // simple | plateau | bundle | configurable

  // AI pipeline fields
  menu_step: "Apéritifs",       // derived — will use Carrefour field once confirmed
  is_food: true,
  dietary_tags: ["sans poisson"],
  allergens: [],                // empty until Carrefour populates type_allergene
  persons: 4,
  price_ref: 4.90,

  // Product details
  department: "Charcuterie",
  image_url: "https://traiteur.carrefour.fr/media/catalog/product/...",
  categories: [{ id: 85, name: "Les plateaux de charcuterie" }],
  composition: { title: "...", pieces: [...] },

  // Future Pinecone embedding source
  embed_text: "Plateau entre amis Jambon cuit Chorizo...",

  ingested_at: ISODate,
  raw: { /* full original Carrefour record */ }
}
```

### `prices`
```js
{ product_id: 31, store_id: 338, price: 4.90 }
// Indexes: { store_id, product_id } unique  |  { product_id }
```

### `stores`
```js
{
  _id: 338,
  name: "Carrefour Beauvais - Sud",
  type_label: "Hyper",
  city: "Beauvais",
  is_active: true,
  curated_concepts: ["Boucherie", "Charcuterie & Traiteur", "Pâtisserie"], // from the Concept X Magasin CSV
  geo: { type: "Point", coordinates: [2.108, 49.412] }
}
// Index: { geo: "2dsphere" }
```

## Roadmap

- [ ] Replace `menu_step` heuristic with dedicated Carrefour field (awaiting confirmation)
- [ ] Populate `allergens` once Carrefour fills `type_allergene`
- [ ] Add Pinecone embedding step using `embed_text`
- [ ] Wire store context into the AI pipeline for per-store pricing
