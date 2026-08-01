"""Inspect and purge smoke/fake fixture batches from acquisition workspace DBs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _is_smoke_batch_name(name: str) -> bool:
    lowered = (name or "").lower()
    return any(token in lowered for token in ("smoke", "fake test", "fixture demo"))


def _is_smoke_candidate_json(raw: str) -> bool:
    text = raw or ""
    lowered = text.lower()
    if "smoke test" in lowered or "fake test" in lowered or "smoke-test" in lowered:
        return True
    try:
        payload = json.loads(text)
    except Exception:
        return False
    title = str(payload.get("title") or "")
    url = str(payload.get("purchase_url") or "")
    return "SMOKE TEST" in title or "FAKE TEST" in title or "smoke-test" in url


def inspect(db_path: Path) -> None:
    if not db_path.exists():
        print(f"MISSING {db_path.name}")
        return
    con = sqlite3.connect(db_path)
    try:
        print(f"=== {db_path.name} ===")
        batches = con.execute(
            "SELECT workspace_batch_id, name, total_rows, source_type "
            "FROM acquisition_workspace_batches ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        print("batches:", batches)
        smoke_rows = []
        for row in con.execute(
            "SELECT workspace_batch_id, candidate_json FROM acquisition_candidates"
        ).fetchall():
            if _is_smoke_candidate_json(row[1]):
                try:
                    title = json.loads(row[1]).get("title")
                except Exception:
                    title = "(unparsed)"
                smoke_rows.append((row[0], title))
        print("smoke/fake candidates:", len(smoke_rows), smoke_rows[:5])
    except sqlite3.Error as exc:
        print(f"{db_path.name}: {exc}")
    finally:
        con.close()


def purge(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    con = sqlite3.connect(db_path)
    removed = 0
    try:
        smoke_batch_ids: set[str] = set()
        for batch_id, name, *_rest in con.execute(
            "SELECT workspace_batch_id, name, total_rows, source_type "
            "FROM acquisition_workspace_batches"
        ).fetchall():
            if _is_smoke_batch_name(str(name)):
                smoke_batch_ids.add(str(batch_id))
        for batch_id, raw in con.execute(
            "SELECT workspace_batch_id, candidate_json FROM acquisition_candidates"
        ).fetchall():
            if _is_smoke_candidate_json(raw):
                smoke_batch_ids.add(str(batch_id))

        for batch_id in smoke_batch_ids:
            con.execute(
                "DELETE FROM acquisition_import_events WHERE workspace_batch_id = ?",
                (batch_id,),
            )
            cur = con.execute(
                "DELETE FROM acquisition_candidates WHERE workspace_batch_id = ?",
                (batch_id,),
            )
            removed += cur.rowcount
            con.execute(
                "DELETE FROM acquisition_workspace_batches WHERE workspace_batch_id = ?",
                (batch_id,),
            )
            print(f"purged batch {batch_id} from {db_path.name}")

        orphan_ids = []
        for candidate_id, raw in con.execute(
            "SELECT candidate_id, candidate_json FROM acquisition_candidates"
        ).fetchall():
            if _is_smoke_candidate_json(raw):
                orphan_ids.append(candidate_id)
        for candidate_id in orphan_ids:
            con.execute(
                "DELETE FROM acquisition_candidates WHERE candidate_id = ?",
                (candidate_id,),
            )
            removed += 1
        con.commit()
    except sqlite3.Error as exc:
        print(f"purge failed for {db_path.name}: {exc}")
        con.rollback()
    finally:
        con.close()
    return removed


def main() -> None:
    targets = [
        DATA / "brand_profit.db",
        DATA / "smoke_prototype.db",
        DATA / "empty_ops_verify.db",
    ]
    for path in targets:
        inspect(path)
    print("--- PURGE ---")
    total = 0
    for path in targets:
        total += purge(path)
    print("total candidates removed:", total)
    for path in targets:
        inspect(path)


if __name__ == "__main__":
    main()
