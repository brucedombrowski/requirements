#!/usr/bin/env python3
"""
Validate JSON files against their corresponding schemas.

Usage:
    python tools/validate.py              # Validate all JSON files
    python tools/validate.py --verbose    # Show per-file results
    python tools/validate.py FILE...      # Validate specific files
"""

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
        "controls/*/catalog.json",
    ],
    "schemas/project-selection.schema.json": [
        "templates/project-selection.json",
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


def main():
    verbose = "--verbose" in sys.argv
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

    if failed > 0 or json_bad > 0:
        sys.exit(1)
    else:
        print()
        print("All validations passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
