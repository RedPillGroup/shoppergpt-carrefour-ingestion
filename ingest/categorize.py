"""
LLM-based product categorization for Carrefour Traiteur.

Replaces the static rule-based menu_step_mapping.py with a Gemini call.
Results are cached by product_id in MongoDB — each product is only categorized once.
Subsequent ingests use the cached value instantly.

Auth: same pattern as waib-api/gemini_http.py —
  - GOOGLE_GENAI_USE_VERTEXAI=true + ADC (prod / GCP)
  - GEMINI_API_KEY (dev / local AI Studio)

Usage (called from run.py before transform_product):
    step_cache = batch_categorize(db, raw_products)
    # step_cache: {product_id: menu_step}
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import google.auth
import google.auth.transport.requests
from pymongo import UpdateOne
from pymongo.database import Database

from ingest.log import get_logger

log = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 50    # products per Gemini call
MAX_WORKERS = 10   # parallel Gemini calls
FALLBACK_STEP = "À côté"  # safe fallback for uncategorizable products

VALID_STEPS = {
    "Apéritifs", "Entrées", "Plats", "Plateaux", "Fromages",
    "Desserts", "Boissons", "Pains", "Petit Déj",
    "Table & Déco", "Fleurs", "À côté",
}

# Case-insensitive lookup (model sometimes returns UPPERCASE or mixed case)
_STEP_LOOKUP: dict[str, str] = {s.upper(): s for s in VALID_STEPS}

SYSTEM_PROMPT = """Tu es un expert en traiteur français. Catégorise chaque produit dans exactement un des steps suivants.
Lis attentivement les distinctions — elles sont importantes.

APÉRITIFS : finger food, amuse-bouches, canapés, mini-toasts, verrines, mousses en petits pots (format individuel), chips, crackers, dips, mini-brochettes, petits fours salés, mini-quiches, mini-burgers, pizzas découpées en toasts (ex: "pizza en 60 toasts"), œufs de poisson. Formats petits, à grignoter debout.

ENTRÉES : plats froids ou chauds servis assis en début de repas. Carpaccio, foie gras entier/mi-cuit (en portion), terrine (en tranche), céviche, œufs mimosa, assiette de crudités, saumon fumé en tranche (format assiette, pas toast). Distinctions clés : foie gras en toast → Apéritifs. Saumon fumé en toast → Apéritifs. Saumon fumé en assiette/tranche → Entrées.

PLATS : plats principaux ET accompagnements. Viandes cuisinées (rôti, magret, souris d'agneau…), poissons cuisinés (pavé de saumon, filet…), volailles, lasagnes, gratins, pizzas entières, quiches entières, plats complets, sushis/makis, plateaux japonais. Également : légumes et accompagnements servis avec les plats (haricots verts, pommes de terre, salades vertes, légumes bruts, pois, carottes).

PLATEAUX : plateaux traiteur composés à partager — plateau de charcuterie, plateau du boucher, plateau BBQ, plateau mixte apéro de grande taille.

FROMAGES : fromages à la coupe ou en plateau, raclette, fondue.

DESSERTS : pâtisseries sucrées (gâteaux, tartes, macarons, entremets, éclairs, mille-feuilles, bûches, mignardises sucrées, fruits en dessert, coupes glacées). NE PAS inclure les viennoiseries du matin.

BOISSONS : toutes les boissons — eau, jus, sodas, champagne, vins, bières, cafés, thés, infusions.

PAINS : pain au sens strict — baguette, pain de campagne, pain de mie, pain aux céréales, pain surprise, pain de seigle, focaccia, pain burger (nature). PAS les viennoiseries.

PETIT DÉJ : viennoiseries (croissants, pains au chocolat, brioches, pains aux raisins, kouign-amann), assortiments petit-déjeuner, coffee break, paniers matinaux, chouquettes, madeleines, financiers. Produits consommés au petit-déjeuner ou à la pause café.

TABLE & DÉCO : vaisselle jetable, assiettes, gobelets, couverts plastique, serviettes en papier, nappes, chemins de table, bougies, ballons, décorations de fête. Également : produits ménagers (éponges, liquide vaisselle, sacs poubelle), ethylotests, et tout article non comestible.

FLEURS : bouquets de fleurs, compositions florales, plantes.

À CÔTÉ : UNIQUEMENT sauces (mayonnaise, ketchup, nuoc-mâm, tapenade, anchoïade…), condiments (moutarde, cornichons…), épices, sel, poivre, sucre, beurre, bonbons et confiseries. PAS les accompagnements alimentaires (légumes, salades) qui vont dans PLATS.

Réponds UNIQUEMENT avec du JSON valide où les clés sont les NUMÉROS des produits (pas les noms) :
{"1": "Desserts", "2": "Boissons", "3": "Apéritifs", ...}
Utilise exactement les noms de steps (avec accents et majuscules).
En cas de doute absolu, utilise "À côté"."""

# ── Auth helpers (mirrors waib-api/gemini_http.py) ────────────────────────────

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _use_vertex() -> bool:
    return os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes"}


def _vertex_url(model: str) -> str:
    project = (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "").strip()
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT must be set when GOOGLE_GENAI_USE_VERTEXAI=true")
    location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "global").strip()
    host = "https://aiplatform.googleapis.com" if location == "global" else f"https://{location}-aiplatform.googleapis.com"
    return f"{host}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"


def _ai_studio_url(model: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set GOOGLE_GENAI_USE_VERTEXAI=true with ADC, or set GEMINI_API_KEY")
    return f"{_AI_STUDIO_BASE}/{model}:generateContent?key={urllib.parse.quote(api_key)}"


def _make_request(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to Gemini generateContent with Vertex ADC or AI Studio key."""
    url = _vertex_url(model) if _use_vertex() else _ai_studio_url(model)
    headers = {"Content-Type": "application/json"}

    if _use_vertex():
        creds, _ = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
        if not creds.token:
            raise RuntimeError("ADC did not return an access token")
        headers["Authorization"] = f"Bearer {creds.token}"

    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


# ── Gemini batch call ─────────────────────────────────────────────────────────

def _format_product(i: int, raw: dict) -> str:
    name = raw.get("name") or ""
    dept = raw.get("carrefour_suppliers_department") or ""
    cats = [c.get("category_name", "") for c in (raw.get("categories") or []) if c.get("category_name")]
    cats_str = ", ".join(cats[:4]) if cats else "aucune"
    return f'{i}. Nom: "{name}" | Département: "{dept}" | Catégories: [{cats_str}]'


def _call_batch(batch: list[tuple[int, dict]]) -> dict[int, str]:
    """Call Gemini for a batch of (index, raw_product) pairs. Returns {index: step}."""
    lines = [_format_product(i, raw) for i, raw in batch]
    prompt = f"{SYSTEM_PROMPT}\n\nProduits :\n" + "\n".join(lines)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }

    for attempt in range(3):
        try:
            response = _make_request(GEMINI_MODEL, payload)
            text = response["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            result = {}
            for k, v in parsed.items():
                try:
                    idx = int(k)
                except (ValueError, TypeError):
                    continue  # skip keys that are product names instead of indices
                # Normalize casing (model sometimes returns UPPERCASE)
                normalized = _STEP_LOOKUP.get(str(v).upper().strip(), FALLBACK_STEP)
                result[idx] = normalized
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < 2:
                time.sleep(2 ** attempt * 2)
                continue
            log.warning("gemini_batch_http_error", code=exc.code, batch_size=len(batch))
            return {i: FALLBACK_STEP for i, _ in batch}
        except Exception as exc:
            if attempt < 2:
                time.sleep(1.5 ** attempt)
                continue
            log.warning("gemini_batch_failed", error=str(exc), batch_size=len(batch))
            return {i: FALLBACK_STEP for i, _ in batch}

    return {i: FALLBACK_STEP for i, _ in batch}


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache(db: Database, product_ids: list[int]) -> dict[int, str]:
    cached = {}
    for doc in db.products.find(
        {"_id": {"$in": product_ids}, "menu_step": {"$ne": None}, "menu_step_source": "llm"},
        {"_id": 1, "menu_step": 1},
    ):
        cached[doc["_id"]] = doc["menu_step"]
    return cached


def _save_cache(db: Database, step_map: dict[int, str]) -> None:
    ops = [
        UpdateOne({"_id": pid}, {"$set": {"menu_step": step, "menu_step_source": "llm"}})
        for pid, step in step_map.items()
    ]
    if ops:
        db.products.bulk_write(ops, ordered=False)


# ── Public API ────────────────────────────────────────────────────────────────

def batch_categorize(
    db: Database,
    raw_products: list[dict],
    force: bool = False,
) -> dict[int, str]:
    """Categorize all products via Gemini, using MongoDB cache for already-seen SKUs.

    Auth: Vertex AI + ADC if GOOGLE_GENAI_USE_VERTEXAI=true, else GEMINI_API_KEY.

    Args:
        db: MongoDB database handle.
        raw_products: List of raw JSONL dicts (must have ``product_id``).
        force: If True, ignore cache and re-categorize everything.

    Returns:
        Dict mapping product_id → menu_step for all input products.
    """
    all_ids = [int(r["product_id"]) for r in raw_products]
    id_to_raw = {int(r["product_id"]): r for r in raw_products}

    cached: dict[int, str] = {} if force else _load_cache(db, all_ids)
    to_classify = [pid for pid in all_ids if pid not in cached]

    auth_mode = "vertex+ADC" if _use_vertex() else "AI Studio key"
    log.info(
        "categorize_start",
        total=len(all_ids),
        from_cache=len(cached),
        via_llm=len(to_classify),
        auth=auth_mode,
    )

    if not to_classify:
        return cached

    indexed = [(i, id_to_raw[pid]) for i, pid in enumerate(to_classify, start=1)]
    batches = [indexed[i:i + BATCH_SIZE] for i in range(0, len(indexed), BATCH_SIZE)]
    log.info("categorize_batches", batches=len(batches), workers=min(MAX_WORKERS, len(batches)))

    index_to_pid = {i: pid for i, pid in enumerate(to_classify, start=1)}
    llm_results: dict[int, str] = {}

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as executor:
        futures = {executor.submit(_call_batch, batch): batch for batch in batches}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            llm_results.update(future.result())
            log.info("categorize_progress", batches_done=completed, total_batches=len(batches))

    llm_by_pid = {index_to_pid[idx]: step for idx, step in llm_results.items() if idx in index_to_pid}
    _save_cache(db, llm_by_pid)

    final = {**cached, **llm_by_pid}

    dist: dict[str, int] = {}
    for step in final.values():
        dist[step] = dist.get(step, 0) + 1
    log.info("categorize_complete", from_cache=len(cached), via_llm=len(llm_by_pid), distribution=dist)

    return final
