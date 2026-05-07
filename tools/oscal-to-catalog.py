#!/usr/bin/env python3
"""Transform a NIST OSCAL catalog JSON into the project's controls/<id>/catalog.json shape.

Reads an OSCAL catalog (e.g., NIST_SP-800-53_rev5_catalog.json) and emits a
flat control map keyed by the human-readable control ID (e.g., AC-1, AC-1(1),
03.01.01) with family / title / description / derived_from. Records the
upstream OSCAL path and SHA-256 in the catalog's `source` block so consumers
can verify the catalog was generated from a specific upstream artifact.

Usage:
    python tools/oscal-to-catalog.py --oscal sources/nist/oscal/NIST_SP-800-53_rev5_catalog.json \\
                                     --out   controls/nist-800-53/catalog.json \\
                                     --standard "NIST SP 800-53 Rev 5" \\
                                     --url     https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Control IDs in NIST 800-53 publications (e.g., "AC-1", "AC-1(1)").
SP800_53_PATTERN = re.compile(r"^[A-Z]{2}-\d+(\(\d+\))?$")


def label(control: dict) -> str:
    """Pick the human-readable control ID (AC-1, AC-1(1), 03.01.01).

    NIST OSCAL is inconsistent across catalogs:
      - 800-53 r5: label="AC-1" (and a zero-padded variant); sort-id="ac-01"
      - 800-171 r3: label="Account Management (03.01.01)"; sort-id="03.01.01"

    Strategy: try label props first (parenthetical or clean form),
    then fall back to a normalized sort-id.
    """
    for prop in control.get("props", []):
        if prop.get("name") != "label":
            continue
        if prop.get("class") == "zero-padded":
            continue
        v = prop["value"]
        # 800-53 form: "AC-1" or "AC-1(1)" — try BEFORE the parenthetical
        # extraction below, since AC-2(1)'s "(1)" is the enhancement number.
        if re.match(r"^[A-Z]{2}-\d+(\(\d+\))?$", v):
            return v
        # 800-171 form: "Account Management (03.01.01)"
        m = re.search(r"\(([\d.]+)\)\s*$", v)
        if m:
            return m.group(1)

    for prop in control.get("props", []):
        if prop.get("name") != "sort-id":
            continue
        v = prop["value"]
        # 800-53 style: "ac-01" -> "AC-1"
        m = re.match(r"^([a-z]{2})-0*(\d+)$", v)
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}"
        # 800-53 enhancement: "ac-01.01" -> "AC-1(1)"
        m = re.match(r"^([a-z]{2})-0*(\d+)\.0*(\d+)$", v)
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}({m.group(3)})"
        return v

    return control["id"].upper()


def render_prose(prose: str, params_by_id: dict) -> str:
    """Substitute OSCAL parameter placeholders with their human-readable label."""
    def sub(match):
        pid = match.group(1).strip()
        p = params_by_id.get(pid)
        if not p:
            return f"[{pid}]"
        guideline = ""
        if p.get("guidelines"):
            guideline = p["guidelines"][0].get("prose", "")
        return f"[{p.get('label') or guideline or pid}]"
    return re.sub(r"\{\{\s*insert:\s*param,\s*([^}]+?)\s*\}\}", sub, prose)


def collect_statement(parts: list, params_by_id: dict) -> str:
    """Recursively concatenate all 'statement' / 'item' part prose."""
    out = []

    def walk(plist):
        for p in plist:
            name = p.get("name")
            if name in {"statement", "item"}:
                if "prose" in p:
                    out.append(render_prose(p["prose"], params_by_id))
                if "parts" in p:
                    walk(p["parts"])

    walk(parts)
    return " ".join(t.strip() for t in out if t.strip()).strip()


def build_resource_index(back_matter: dict) -> dict:
    """uuid -> resource title (used to resolve link refs)."""
    out = {}
    for r in back_matter.get("resources", []):
        out[r["uuid"]] = r.get("title", "")
    return out


def cross_refs(control: dict, resource_index: dict) -> list[str]:
    """Resolve link refs that look like 800-53 control citations (AC-1, AC-1(1))."""
    out = []
    seen = set()
    for link in control.get("links", []):
        rel = link.get("rel")
        if rel not in {"reference", "related", "required"}:
            continue
        href = link.get("href", "")
        if not href.startswith("#"):
            continue
        title = resource_index.get(href[1:], "")
        # Some titles use zero-padded forms like "AC-01" or "AC-01(01)" — normalize.
        normalized = re.sub(r"\b([A-Z]{2})-0*(\d+)", r"\1-\2", title)
        normalized = re.sub(r"\(0*(\d+)\)", r"(\1)", normalized)
        if SP800_53_PATTERN.match(normalized) and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return sorted(out)


def collect_params(controls: list) -> dict:
    out = {}
    def walk(clist):
        for c in clist:
            for p in c.get("params", []):
                out[p["id"]] = p
            if "controls" in c:
                walk(c["controls"])
    walk(controls)
    return out


def emit_controls(group: dict, group_title: str, params_by_id: dict, resource_index: dict, out: dict):
    for control in group.get("controls", []):
        ctrl_label = label(control)
        title = control.get("title", "").strip()
        description = collect_statement(control.get("parts", []), params_by_id)
        if not description:
            description = title
        entry = {
            "family": group_title,
            "title": title,
            "description": description,
        }
        related = cross_refs(control, resource_index)
        if related:
            entry["derived_from"] = related
        out[ctrl_label] = entry
        # Recurse into control enhancements.
        emit_controls(control, group_title, params_by_id, resource_index, out)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oscal", required=True, help="Path to OSCAL catalog JSON (relative to repo root)")
    ap.add_argument("--out", required=True, help="Output catalog.json path (relative to repo root)")
    ap.add_argument("--standard", required=True, help="Standard label (e.g., 'NIST SP 800-53 Rev 5')")
    ap.add_argument("--url", required=True, help="Canonical publication URL")
    ap.add_argument("--title", help="Override the catalog title (defaults to OSCAL metadata title)")
    ap.add_argument("--notes", help="Free-form notes (e.g., scope caveats)")
    args = ap.parse_args()

    oscal_path = REPO_ROOT / args.oscal
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(oscal_path) as f:
        oscal = json.load(f)

    catalog = oscal["catalog"]
    metadata = catalog.get("metadata", {})
    resource_index = build_resource_index(catalog.get("back-matter", {}))

    # Collect every parameter so prose substitution can resolve placeholders.
    all_params = {}
    def walk_groups(groups):
        for g in groups:
            all_params.update(collect_params(g.get("controls", [])))
            if "groups" in g:
                walk_groups(g["groups"])
    walk_groups(catalog.get("groups", []))

    controls_out: dict = {}
    for group in catalog.get("groups", []):
        emit_controls(group, group.get("title", ""), all_params, resource_index, controls_out)

    out_doc = {
        "standard": args.standard,
        "title": args.title or metadata.get("title", args.standard),
        "url": args.url,
        "source": {
            "path": args.oscal,
            "sha256": sha256_file(oscal_path),
            "generator": "tools/oscal-to-catalog.py",
            "generated_at": dt.date.today().isoformat(),
        },
        "controls": controls_out,
    }
    if args.notes:
        out_doc["source"]["notes"] = args.notes

    out_path.write_text(json.dumps(out_doc, indent=2) + "\n")
    print(f"Wrote {out_path.relative_to(REPO_ROOT)}: {len(controls_out)} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
