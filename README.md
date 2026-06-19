# shopper-gpt-carrefour-ingest

ETL pipeline that ingests the Carrefour Traiteur JSONL exports into MongoDB.

## What it does

Reads 3 daily JSONL exports from Carrefour and upserts them into 3 MongoDB collections:

| Export | Collection | Description |
|---|---|---|
| `products.jsonl` | `products` | Normalised product catalogue |
| `products_prices.jsonl` | `prices` | Per-store pricing matrix |
| `stores.jsonl` | `stores` | Store reference data |

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

## Run

```bash
# Ingest everything
poetry run python run.py

# Or one collection at a time
poetry run python run.py --stores
poetry run python run.py --prices
poetry run python run.py --force-categorize
poetry run python run.py --products
poetry run python run.py --pinecone --reset-pinecone

## Data files

Place the JSONL exports in the `data/` folder (gitignored):

```
data/
├── products.jsonl
├── products_prices.jsonl
└── stores.jsonl
```

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
  geo: { type: "Point", coordinates: [2.108, 49.412] }
}
// Index: { geo: "2dsphere" }
```

## Roadmap

- [ ] Replace `menu_step` heuristic with dedicated Carrefour field (awaiting confirmation)
- [ ] Populate `allergens` once Carrefour fills `type_allergene`
- [ ] Add Pinecone embedding step using `embed_text`
- [ ] Wire store context into the AI pipeline for per-store pricing
