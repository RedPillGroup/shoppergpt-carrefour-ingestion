"""
Carrefour's curated business taxonomy — 17 store-level product "Concepts"
(Boucherie, Charcuterie & Traiteur, Plateaux de fromages, Number & Letter
Cakes, ...). Completely different from the messy raw ``concepts`` field
already present in the store JSONL export (internal logistics labels like
"JeNEfabriquePASlespetitsfours") — this is Carrefour's own clean business
taxonomy, exported as flat CSVs in ``data/``:

* Concept X Magasin    — store_id -> set of concepts actually carried there
* Evénement X Concept  — 13 occasions x 18 concepts fit-score matrix (0-100)

``load_store_concepts`` feeds the ``curated_concepts`` field into the ingest
pipeline (see transform.py's transform_store) — used purely as an
informational signal in waib-api (store-availability hints for the query
planner and live_context), never as a candidate filter.

The Concept X Produits per-product join was tried and dropped: tagging every
product with a single curated concept and using it to rerank/filter search
candidates had no measurable effect (the composer LLM reasons over full
candidate pools regardless of order) and risked wrongly excluding good
candidates. The Événement x Concept matrix is small and effectively static —
it isn't ingested at all, it's hardcoded as ``EVENT_CONCEPT_FIT`` directly in
waib-api's engine.py.
"""

import csv
from pathlib import Path

from ingest.config import CONCEPT_MAGASIN_FILE
from ingest.log import get_logger

log = get_logger(__name__)

_ACTIVE = "Activé"


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, list(reader)


def load_store_concepts() -> dict[int, set[str]]:
    """Return ``{store_id: {concept_name, ...}}`` — every concept actually
    carried by that store. Skips stores whose ``Statut`` is "Désactivé"."""
    if not CONCEPT_MAGASIN_FILE.exists():
        log.warning("concept_magasin_file_missing", path=str(CONCEPT_MAGASIN_FILE))
        return {}

    header, rows = _read_csv(CONCEPT_MAGASIN_FILE)
    concept_columns = header[3:]

    result: dict[int, set[str]] = {}
    for row in rows:
        if row[2] != _ACTIVE:
            continue
        try:
            store_id = int(row[0])
        except (ValueError, IndexError):
            continue
        concepts = {
            concept
            for concept, flag in zip(concept_columns, row[3 : 3 + len(concept_columns)])
            if flag == "1"
        }
        result[store_id] = concepts
    return result
