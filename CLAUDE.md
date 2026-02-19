# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and AI agents working in this repository.

## Project Overview

Requirements catalog — a library of requirements decomposed from open standards (NIST, FIPS, NASA NPR/NID). Projects select which requirements they need via `project-selection.json`.

## Commands

```bash
# Validate all JSON files against schemas
python tools/validate.py

# Verbose validation
python tools/validate.py --verbose

# Validate specific file
python tools/validate.py catalog/nasa/npr-2810-7/requirements.json
```

## Repository Structure

- `schemas/` — JSON Schema (draft-2020-12) definitions for all file types
- `standards/` — Standard metadata (one file per standard, referenced by ID)
- `controls/` — NIST control definitions (definition-only, no implementation blocks)
- `catalog/` — The requirements library organized by issuing authority and document
- `templates/` — Templates for consuming projects
- `tools/` — Validation tooling

## Key Conventions

### Schema Design
- Requirement sets use `catalog_info` (not `document`) as the top-level metadata key
- Requirements are stored as **arrays** to preserve source document ordering
- Standards are referenced by `id` field matching filenames in `standards/`
- Control catalogs contain **no implementation blocks** — those belong in consuming projects

### Adding Requirements
1. Create a directory under `catalog/<authority>/<document-id>/`
2. Add `requirements.json` following `schemas/requirement-set.schema.json`
3. Add `README.md` with context about the source document
4. Reference standards by ID (add to `standards/` if new)
5. Run `python tools/validate.py` to verify

### Adding Controls
1. Create a directory under `controls/<standard-id>/`
2. Add `catalog.json` following `schemas/control.schema.json`
3. Include only: family, title, description, derived_from
4. Never include implementation details

### File Naming
- Standard files: `<short-id>.json` (e.g., `nist-sp-800-53-r5.json`)
- Control directories: `<standard-short-name>/` (e.g., `nist-800-53/`)
- Catalog directories: `<authority>/<document-id>/` (e.g., `nasa/npr-2810-7/`)

## Relationships to Other Repos

| Repo | Relationship |
|------|-------------|
| systems-engineering | Defines requirements process (how) |
| LaTeX | Consumes requirements for PDF generation |
| Security | Consumes requirements for toolkit traceability |
| NPR2810.7 | Independent document review (GitHub issues) |
