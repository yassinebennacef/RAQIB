"""Append-only, hash-chained log of officer decisions (artifacts/decisions.jsonl).

hash = sha256(prev_hash + canonical JSON of the record without its hash).
Altering, deleting or reordering any past line breaks verify().
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config as C

GENESIS = "0" * 64
DECISIONS = ("INSPECT", "DOCUMENT_CHECK", "RELEASE")
_LOCK = threading.Lock()


def canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(prev_hash: str, record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256((prev_hash + canonical(body)).encode("utf-8")).hexdigest()


def read_all(path: Path | None = None) -> list[dict]:
    path = path or C.DECISIONS_LOG
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def append(declaration_id: str, decision: str, comment: str = "", officer: str = "Officer",
           ai: dict | None = None, path: Path | None = None) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    path = path or C.DECISIONS_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        entries = read_all(path)
        prev = entries[-1]["hash"] if entries else GENESIS
        record = {
            "id": len(entries) + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "declaration_id": str(declaration_id),
            "decision": decision,
            "comment": comment or "",
            "officer": officer or "Officer",
            "ai": ai or {},
            "prev_hash": prev,
        }
        record["hash"] = compute_hash(prev, record)
        with path.open("a", encoding="utf-8") as f:
            f.write(canonical(record) + "\n")
    return record


def verify(path: Path | None = None) -> dict:
    entries = read_all(path)
    prev = GENESIS
    for e in entries:
        if e.get("prev_hash") != prev or compute_hash(prev, e) != e.get("hash"):
            return {"ok": False, "n_entries": len(entries), "first_bad_id": e.get("id")}
        prev = e["hash"]
    return {"ok": True, "n_entries": len(entries), "first_bad_id": None}
