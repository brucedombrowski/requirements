#!/usr/bin/env python3
"""
Validate JSON files against their corresponding schemas.

Usage:
    python tools/validate.py              # Validate all JSON files
    python tools/validate.py --verbose    # Show per-file results
    python tools/validate.py --graph      # Also validate authority graph
    python tools/validate.py --sources    # Also verify SHA-256 of source PDFs
    python tools/validate.py FILE...      # Validate specific files
"""

import hashlib
import json
import os
import sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError, Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_MAP = {
    "schemas/requirement-set.schema.json": [
        "catalog/**/requirements.json",
    ],
    "schemas/standard.schema.json": [
        "standards/*.json",
    ],
    "schemas/control.schema.json": [
        "controls/**/catalog.json",
    ],
    "schemas/project-selection.schema.json": [
        "templates/project-selection.json",
    ],
    "schemas/cui-registry.schema.json": [
        "registries/nara-cui/registry.json",
    ],
}


def load_json(path):
    """Load and parse a JSON file."""
    with open(path) as f:
        return json.load(f)


def structural_validate(data, schema_name):
    """Fallback validation when jsonschema is not installed.

    Checks that required top-level keys exist.
    """
    errors = []
    if "required" in load_json(REPO_ROOT / schema_name):
        required = load_json(REPO_ROOT / schema_name)["required"]
        for key in required:
            if key not in data:
                errors.append(f"Missing required key: {key}")
    return errors


def find_files(pattern):
    """Find files matching a glob pattern relative to repo root."""
    return sorted(REPO_ROOT.glob(pattern))


def validate_file(filepath, schema_path, verbose=False):
    """Validate a single JSON file against a schema. Returns (pass, errors)."""
    try:
        data = load_json(filepath)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    if HAS_JSONSCHEMA:
        try:
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
            validate(instance=data, schema=schema)
            return True, []
        except ValidationError as e:
            return False, [f"{e.json_path}: {e.message}"]
    else:
        errors = structural_validate(data, schema_path)
        if errors:
            return False, errors
        return True, []


def load_standards():
    """Load all standard JSON files and return as dict keyed by id."""
    standards = {}
    standards_dir = REPO_ROOT / "standards"
    for path in sorted(standards_dir.glob("*.json")):
        if path.name == "README.md":
            continue
        with open(path) as f:
            data = json.load(f)
        standards[data["id"]] = data
    return standards


def validate_graph(verbose=False):
    """Validate authority graph relationships.

    Checks:
    1. Dangling references — all derives_from/references IDs must exist
    2. Cycle detection — derives_from edges must form a DAG
    3. Tier consistency — derives_from edges should point to equal-or-lower tier
    4. Orphan warning — standards with no authority edges
    """
    standards = load_standards()
    known_ids = set(standards.keys())
    errors = []
    warnings = []

    # Collect derives_from edges for cycle detection
    derives_graph = {}  # id -> list of parent ids

    for sid, std in standards.items():
        authority = std.get("authority", {})
        derives_from = authority.get("derives_from", [])
        references = authority.get("references", [])
        parent_ids = []

        # Check derives_from edges
        for edge in derives_from:
            target_id = edge["id"]
            if target_id not in known_ids:
                errors.append(
                    f"Dangling derives_from: {sid} -> {target_id} (not found in standards/)"
                )
            parent_ids.append(target_id)

            # Tier consistency
            src_tier = std.get("tier")
            tgt_std = standards.get(target_id, {})
            tgt_tier = tgt_std.get("tier")
            if src_tier is not None and tgt_tier is not None:
                if tgt_tier > src_tier:
                    errors.append(
                        f"Tier violation: {sid} (tier {src_tier}) derives_from "
                        f"{target_id} (tier {tgt_tier}) — parent should be equal or lower tier"
                    )

        derives_graph[sid] = parent_ids

        # Check references edges
        for edge in references:
            target_id = edge["id"]
            if target_id not in known_ids:
                errors.append(
                    f"Dangling reference: {sid} -> {target_id} (not found in standards/)"
                )

        # Orphan check
        has_derives = len(derives_from) > 0
        has_refs = len(references) > 0
        is_referenced = False
        for other_sid, other_std in standards.items():
            if other_sid == sid:
                continue
            other_auth = other_std.get("authority", {})
            for e in other_auth.get("derives_from", []):
                if e["id"] == sid:
                    is_referenced = True
                    break
            if not is_referenced:
                for e in other_auth.get("references", []):
                    if e["id"] == sid:
                        is_referenced = True
                        break
            if is_referenced:
                break

        if not has_derives and not has_refs and not is_referenced:
            warnings.append(f"Orphan: {sid} has no authority edges (disconnected from graph)")

    # Cycle detection via DFS
    visited = set()
    in_stack = set()

    def has_cycle(node, path):
        if node in in_stack:
            cycle = path[path.index(node):]
            cycle.append(node)
            errors.append(f"Cycle detected in derives_from: {' -> '.join(cycle)}")
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for parent in derives_graph.get(node, []):
            if parent in known_ids:
                if has_cycle(parent, path + [node]):
                    return True
        in_stack.discard(node)
        return False

    for sid in standards:
        if sid not in visited:
            has_cycle(sid, [])

    return errors, warnings


def validate_sources():
    """Verify each standard's local_copy file exists and matches its sha256.

    Returns (errors, warnings).
    """
    standards = load_standards()
    errors = []
    warnings = []

    for sid, std in standards.items():
        local_copy = std.get("local_copy")
        sha256 = std.get("sha256")
        if not local_copy:
            if not sha256:
                continue  # No local copy claimed; nothing to verify.
            errors.append(f"{sid}: sha256 set without local_copy")
            continue

        path = REPO_ROOT / local_copy
        if not path.exists():
            errors.append(f"{sid}: local_copy missing: {local_copy}")
            continue

        if not sha256:
            warnings.append(f"{sid}: local_copy set without sha256 (cannot verify integrity)")
            continue

        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != sha256:
            errors.append(
                f"{sid}: sha256 mismatch for {local_copy} "
                f"(expected {sha256[:12]}…, got {actual[:12]}…)"
            )

    return errors, warnings


def main():
    verbose = "--verbose" in sys.argv
    run_graph = "--graph" in sys.argv
    run_sources = "--sources" in sys.argv
    specific_files = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not HAS_JSONSCHEMA:
        print("WARNING: jsonschema not installed. Using structural validation only.")
        print("  Install with: pip install jsonschema")
        print()

    total = 0
    passed = 0
    failed = 0
    errors_list = []

    if specific_files:
        # Validate specific files — auto-detect schema
        for filepath in specific_files:
            filepath = Path(filepath).resolve()
            rel = filepath.relative_to(REPO_ROOT)
            schema_path = None
            for schema, patterns in SCHEMA_MAP.items():
                for pattern in patterns:
                    if filepath in find_files(pattern):
                        schema_path = REPO_ROOT / schema
                        break
                if schema_path:
                    break

            if not schema_path:
                print(f"  SKIP  {rel} (no matching schema)")
                continue

            total += 1
            ok, errs = validate_file(filepath, schema_path, verbose)
            if ok:
                passed += 1
                if verbose:
                    print(f"  PASS  {rel}")
            else:
                failed += 1
                errors_list.append((rel, errs))
                print(f"  FAIL  {rel}")
                for e in errs:
                    print(f"        {e}")
    else:
        # Validate all mapped files
        for schema_rel, patterns in SCHEMA_MAP.items():
            schema_path = REPO_ROOT / schema_rel
            if not schema_path.exists():
                print(f"  WARN  Schema not found: {schema_rel}")
                continue

            for pattern in patterns:
                for filepath in find_files(pattern):
                    rel = filepath.relative_to(REPO_ROOT)
                    # Skip README files
                    if filepath.name == "README.md":
                        continue
                    total += 1
                    ok, errs = validate_file(filepath, schema_path, verbose)
                    if ok:
                        passed += 1
                        if verbose:
                            print(f"  PASS  {rel}")
                    else:
                        failed += 1
                        errors_list.append((rel, errs))
                        print(f"  FAIL  {rel}")
                        for e in errs:
                            print(f"            {e}")

    # Also validate that all JSON files are at least valid JSON
    print()
    print("--- JSON syntax check ---")
    json_files = list(REPO_ROOT.glob("**/*.json"))
    json_files = [f for f in json_files if ".git" not in str(f)]
    json_total = 0
    json_bad = 0
    for jf in sorted(json_files):
        json_total += 1
        try:
            load_json(jf)
            if verbose:
                print(f"  OK    {jf.relative_to(REPO_ROOT)}")
        except json.JSONDecodeError as e:
            json_bad += 1
            print(f"  BAD   {jf.relative_to(REPO_ROOT)}: {e}")

    print(f"  {json_total} JSON files checked, {json_total - json_bad} valid, {json_bad} invalid")

    # Summary
    print()
    print("--- Schema validation summary ---")
    print(f"  {total} files validated against schemas")
    print(f"  {passed} passed, {failed} failed")

    if errors_list:
        print()
        print("Failures:")
        for rel, errs in errors_list:
            print(f"  {rel}:")
            for e in errs:
                print(f"    - {e}")

    # Authority graph validation
    graph_errors = 0
    if run_graph:
        print()
        print("--- Authority graph validation ---")
        errors, warnings = validate_graph(verbose)
        for w in warnings:
            print(f"  WARN  {w}")
        for e in errors:
            print(f"  FAIL  {e}")
            graph_errors += 1
        if not errors and not warnings:
            print("  All graph checks passed.")
        elif not errors:
            print(f"  {len(warnings)} warnings, 0 errors")
        else:
            print(f"  {len(warnings)} warnings, {graph_errors} errors")

    # Source-document integrity verification
    source_errors = 0
    if run_sources:
        print()
        print("--- Source document integrity ---")
        errors, warnings = validate_sources()
        for w in warnings:
            print(f"  WARN  {w}")
        for e in errors:
            print(f"  FAIL  {e}")
            source_errors += 1
        if not errors and not warnings:
            print("  All source SHA-256 digests verified.")
        elif not errors:
            print(f"  {len(warnings)} warnings, 0 errors")
        else:
            print(f"  {len(warnings)} warnings, {source_errors} errors")

    if failed > 0 or json_bad > 0 or graph_errors > 0 or source_errors > 0:
        sys.exit(1)
    else:
        print()
        print("All validations passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
