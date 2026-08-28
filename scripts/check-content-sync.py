#!/usr/bin/env python3
"""
paulmress.com content sync-status checker.

scripts/content-manifest.json records, for every Drive-managed page, the
Drive doc's modifiedTime as of the last session that actually read that
doc and confirmed/updated the live page ("drive_modified" / "last_synced").
This script compares that recorded snapshot against a FRESH snapshot of
the same Drive docs' modifiedTime and reports which pages have Drive edits
that haven't been reflected on the live site yet.

This script does NOT call the Google Drive API itself — Claude sessions
read Drive through the mcp__Google_Drive__* connector, not a service
account this script could authenticate as. Instead:

  1. A Claude session fetches fresh metadata for every drive_doc_id in the
     manifest (mcp__Google_Drive__get_file_metadata, or a search) and
     writes it to a small JSON snapshot file, e.g.:

       {
         "18Vk87dXJEIOyk7HDsxZ2ij90KDkQco2SkaDHn-BdWVo": "2026-08-25T19:21:49.438Z",
         "1rnFIoeLAwW8aRBD-NM1wwz16QlMBjaoV8fNGG1Sjo9k": "2026-08-26T09:03:11.000Z"
       }

     (doc_id -> current modifiedTime, for as many manifest docs as were
     checked — a partial snapshot is fine, unlisted ids are just skipped).

  2. Run: python3 scripts/check-content-sync.py path/to/snapshot.json

  3. Anything reported "DRIFTED" has been edited in Drive since a session
     last confirmed the live page reflects it — re-read that doc and
     update the page (or the manifest, if the edit turns out immaterial).

Usage:
  python3 scripts/check-content-sync.py <snapshot.json>   (run from repo root)

Exit code is non-zero if any tracked doc has drifted, so this is
hook/CI-friendly the same way audit-site.py is.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "scripts" / "content-manifest.json"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def all_tracked_docs(manifest):
    """Yield (doc_id, title, recorded_modified, label) for every doc the
    manifest tracks — page briefs and reference docs alike."""
    for page in manifest.get("pages", []):
        yield (
            page["drive_doc_id"],
            page["drive_doc_title"],
            page["drive_modified"],
            page["path"],
        )
    for ref in manifest.get("reference_docs", []):
        yield (
            ref["drive_doc_id"],
            ref["drive_doc_title"],
            ref["drive_modified"],
            ref.get("applies_to", "(reference doc)"),
        )


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    snapshot_path = Path(sys.argv[1])
    if not snapshot_path.exists():
        print(f"Snapshot file not found: {snapshot_path}")
        sys.exit(2)

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    manifest = load_manifest()

    drifted = []
    unchanged = []
    not_in_snapshot = []

    for doc_id, title, recorded_modified, label in all_tracked_docs(manifest):
        if doc_id not in snapshot:
            not_in_snapshot.append((doc_id, title, label))
            continue
        fresh_modified = snapshot[doc_id]
        if fresh_modified > recorded_modified:
            drifted.append((doc_id, title, label, recorded_modified, fresh_modified))
        else:
            unchanged.append((title, label))

    if drifted:
        print("CONTENT DRIFT — these Drive docs were edited after the live site was last synced to them:")
        for doc_id, title, label, old, new in drifted:
            print(f"  {title}  ({label})")
            print(f"    manifest recorded: {old}")
            print(f"    drive now shows:   {new}")
        print()

    if not_in_snapshot:
        print(f"Not checked (missing from snapshot — {len(not_in_snapshot)} doc(s)):")
        for doc_id, title, label in not_in_snapshot:
            print(f"  {title}  ({label})")
        print()

    print(f"Unchanged: {len(unchanged)} doc(s) OK.")

    if drifted:
        print(f"\n{len(drifted)} doc(s) have unreflected Drive edits.")
        sys.exit(1)
    else:
        print("\nNo drift found against the provided snapshot.")


if __name__ == "__main__":
    main()
