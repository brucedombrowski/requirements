# Catalog

The requirements library — requirements decomposed from open standards and policy documents.

## Organization

Requirements are organized by issuing authority and document:

```
catalog/
└── nasa/
    ├── npr-2810-7/       # NPR 2810.7 — CUI Requirements (Active)
    └── nid-2810-135/     # NID 2810.135 — CUI Requirements (Expired)
```

## Schema

All `requirements.json` files conform to `schemas/requirement-set.schema.json`.

## Adding New Requirement Sets

1. Create `catalog/<authority>/<document-id>/requirements.json`
2. Follow the schema (see `templates/custom-requirement-set.json` for a template)
3. Add a `README.md` with source document context
4. Reference standards by ID from `standards/`
5. Validate with `python tools/validate.py`
