"""
Fetch the latest Carrefour exports from Google Cloud Storage into ``data/``.

Carrefour drops one dated JSONL(.gz) per stream into
their bucket — one folder each for the catalogue, the stores
(``magasins``) and the price ``mapping``. ``run.py --fetch`` calls
:func:`fetch_latest_exports` before ingesting: for each stream it picks the most
recently updated object, downloads it to
``data/<local_prefix>_<YYYY-MM-DD>.jsonl.gz``, and deletes the stream's previous
local files so ``config._latest_file`` always resolves to what we just pulled.

The pipeline's readers are gzip-aware (see ``run.py:open_jsonl`` and
``transform.py``), so objects are stored compressed exactly as exported — no
decompression step.

Auth uses Application Default Credentials. Locally, run
``gcloud auth application-default login`` (or set
``GOOGLE_APPLICATION_CREDENTIALS=<service-account.json>``). On GKE the job runs in
the same GCP project as the bucket, so the cluster's default service account is
used automatically — no extra credentials needed.
"""

import re
from datetime import date
from pathlib import Path

from google.cloud import storage

from ingest.config import DATA_DIR, GCS_BUCKET, GCS_PROJECT, GCS_STREAMS
from ingest.log import get_logger

log = get_logger(__name__)

_DATA_SUFFIXES = (".jsonl.gz", ".jsonl")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _is_data_object(name: str) -> bool:
    """True for a real export object — a ``.jsonl``/``.jsonl.gz`` file, not the
    zero-byte folder placeholder GCS lists alongside the prefix."""
    return name.endswith(_DATA_SUFFIXES) and not name.endswith("/")


def _date_suffix(blob: storage.Blob) -> str:
    """``YYYY-MM-DD`` for the local filename: prefer the date embedded in the
    object name, else fall back to the object's last-updated date. Zero-padded so
    ``_latest_file``'s lexicographic sort stays chronological."""
    match = _DATE_RE.search(blob.name)
    if match:
        return match.group(1)
    updated = blob.updated or blob.time_created
    return (updated.date() if updated else date.today()).isoformat()


def _local_suffix(blob_name: str) -> str:
    """Preserve ``.jsonl.gz`` vs ``.jsonl`` from the remote object."""
    return ".jsonl.gz" if blob_name.endswith(".jsonl.gz") else ".jsonl"


def fetch_latest_exports() -> dict[str, Path]:
    """Download the newest object of each stream into ``data/``, replacing the
    stream's previous local files. Returns ``{local_prefix: downloaded_path}``.

    Raises if the bucket yields no export for any stream — an empty ingestion is
    never what ``--fetch`` was asked to do, so fail loudly rather than silently
    proceed on stale (or absent) data.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = storage.Client(project=GCS_PROJECT)
    bucket = client.bucket(GCS_BUCKET)

    downloaded: dict[str, Path] = {}
    for folder, local_prefix in GCS_STREAMS.items():
        blobs = [b for b in client.list_blobs(bucket, prefix=f"{folder}/") if _is_data_object(b.name)]
        if not blobs:
            log.warning("fetch_no_files", folder=folder, bucket=GCS_BUCKET)
            continue

        # "Latest" by object update time (folder-name-agnostic), name as tiebreaker.
        latest = max(blobs, key=lambda b: (b.updated or b.time_created, b.name))
        target = DATA_DIR / f"{local_prefix}_{_date_suffix(latest)}{_local_suffix(latest.name)}"

        # Remove the stream's previous local files (dated + legacy names) so
        # _latest_file cannot resolve to a stale export after this refresh.
        for old in [*DATA_DIR.glob(f"{local_prefix}*.jsonl.gz"), *DATA_DIR.glob(f"{local_prefix}*.jsonl")]:
            if old != target:
                old.unlink()
                log.info("fetch_removed_old", file=old.name)

        log.info(
            "fetch_downloading",
            folder=folder,
            remote=latest.name,
            size=latest.size,
            target=target.name,
        )
        latest.download_to_filename(str(target))
        downloaded[local_prefix] = target

    if not downloaded:
        raise RuntimeError(
            f"No exports found in gs://{GCS_BUCKET} (looked in folders: "
            f"{', '.join(GCS_STREAMS)}). Check the bucket, the credentials, and GCS_PROJECT."
        )
    log.info("fetch_complete", streams=len(downloaded))
    return downloaded
