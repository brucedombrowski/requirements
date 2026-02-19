# Controls

NIST control definitions — **definition-only** (no implementation blocks).

Implementation details belong in consuming projects (e.g., Security toolkit). This directory provides the canonical control definitions for cross-referencing.

## Catalogs

| Directory | Standard | Controls |
|-----------|----------|----------|
| `nist-800-53/` | NIST SP 800-53 Rev 5 | 14 controls |
| `nist-800-171/` | NIST SP 800-171 Rev 2 | 11 controls |

## Schema

All `catalog.json` files conform to `schemas/control.schema.json`.

## What's Included vs. Excluded

**Included** (in this repo):
- Control ID, family, title, description
- `derived_from` mappings (800-171 → 800-53)

**Excluded** (stays in consuming projects):
- `implementation` blocks (status, scripts, libraries, notes)
- Project-specific mapping and traceability
