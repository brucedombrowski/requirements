# Requirements Catalog

A catalog/library of requirements decomposed from open standards. Projects select which requirements they need (or create their own).

## Purpose

This repository provides the **content** (what) — the actual requirements from federal standards and NASA policies. It is separate from:

- **systems-engineering** — defines the *process* for requirements (how)
- **LaTeX** — consumes requirements for PDF generation
- **Security** — consumes requirements for toolkit traceability
- **NPR2810.7** — document review tracked via GitHub issues (independent)

## Repository Structure

```
requirements/
├── schemas/                 # JSON schemas (draft-2020-12)
│   ├── requirement-set.schema.json
│   ├── standard.schema.json
│   ├── control.schema.json
│   └── project-selection.schema.json
├── standards/               # Standard metadata (name, URL, version)
│   ├── nist-sp-800-53-r5.json
│   ├── nist-sp-800-171-r2.json
│   └── ...
├── controls/                # NIST control definitions (no implementation)
│   ├── nist-800-53/catalog.json
│   └── nist-800-171/catalog.json
├── catalog/                 # The requirements library
│   └── nasa/
│       ├── npr-2810-7/      # 72 reqs from NPR 2810.7 (Active)
│       └── nid-2810-135/    # 72 reqs from NID 2810.135 (Expired)
├── templates/               # For consuming projects
│   ├── project-selection.json
│   └── custom-requirement-set.json
└── tools/
    └── validate.py          # Validate JSON against schemas
```

## How Projects Consume This Catalog

Projects add this repo as a **git submodule** and create a `project-selection.json`:

```json
{
  "project": { "name": "Security Toolkit", "version": "1.17.0" },
  "selections": [
    { "source": "nasa/npr-2810-7", "include": "mandatory-only" },
    { "source": "nist/sp-800-53-r5", "include": "selected", "requirement_ids": ["AU-2", "CM-8"] }
  ]
}
```

### Adding as a submodule

```bash
git submodule add git@github.com:brucedombrowski/requirements.git requirements
git submodule update --init
```

## Key Design Decisions

- **Evolved from LaTeX JSON schema** — proven with 72 requirements; `document` renamed to `catalog_info`
- **Control catalogs are definition-only** — no `implementation` blocks (those stay in consuming projects)
- **Standards referenced by ID** — defined once in `standards/`, referenced everywhere else
- **Requirements stored as arrays** — preserves source document ordering

## Validation

```bash
# Full validation (requires jsonschema: pip install jsonschema)
python tools/validate.py

# Verbose output
python tools/validate.py --verbose

# Structural validation (no dependencies)
python tools/validate.py
```

## Repo Relationships

```
systems-engineering ─── defines PROCESS (how to do requirements)
         │
         ▼
   requirements ─────── provides CONTENT (the catalog)     [this repo]
      │       │
      │       │         NPR2810.7 ── document review        [independent]
      ▼       ▼
   LaTeX   Security ─── consume via submodule
```
