# NARA CUI Registry

Structured capture of the National Archives CUI (Controlled Unclassified Information) Registry.

## Source

| Field | Value |
|-------|-------|
| Publisher | National Archives and Records Administration (NARA) |
| Authority | Executive Order 13556, 32 CFR Part 2002 |
| URL | https://www.archives.gov/cui |
| Category List Last Reviewed | 2025-03-06 |
| Marking List Last Reviewed | 2024-04-09 |
| Date Accessed | 2026-02-19 |

## Files

| File | Contents |
|------|----------|
| `registry.json` | All 20 organizational index groupings, ~125 categories with marking abbreviations and Basic/Specified banner markings |

## CUI Basic vs CUI Specified

- **CUI Basic**: The authorizing law does not specify particular handling controls. Uniform controls from EO 13556 and 32 CFR 2002 apply. All Basic categories have the same controls.
- **CUI Specified**: The authorizing law contains specific handling controls that differ from Basic. Controls can differ between Specified categories. Where the law is silent, Basic controls apply as default.

## Marking Conventions

- Basic banner: `CUI` or optionally `CUI//CATEGORY` (e.g., `CUI//PRVCY`)
- Specified banner: `CUI//SP-CATEGORY` (e.g., `CUI//SP-CTI`) — the `SP-` prefix is mandatory
- Mixed documents: Specified categories (alphabetized) precede Basic categories (alphabetized) in the banner

## Schema

Validated against `schemas/cui-registry.schema.json`.

## MLA Citations

"CUI Registry: Category List." *National Archives*, National Archives and Records Administration, 6 Mar. 2025, www.archives.gov/cui/registry/category-list. Accessed 19 Feb. 2026.

"CUI Category Marking List." *National Archives*, National Archives and Records Administration, 9 Apr. 2024, www.archives.gov/cui/registry/category-marking-list. Accessed 19 Feb. 2026.
