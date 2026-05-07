# Standards

Standard metadata files. Each standard is defined once here and referenced by `id` throughout the catalog.

## Files

| File | Standard | Type | Tier |
|------|----------|------|------|
| `usc-const.json` | U.S. Constitution | Constitutional provision | 0 |
| `51-usc-20132.json` | 51 U.S.C. §20132 | Statute | 1 |
| `44-usc-ch35.json` | 44 U.S.C. Ch. 35 (FISMA) | Statute | 1 |
| `5-usc-552.json` | 5 U.S.C. §552 (FOIA) | Statute | 1 |
| `5-usc-552a.json` | 5 U.S.C. §552a (Privacy Act) | Statute | 1 |
| `40-usc-11331.json` | 40 U.S.C. §11331 | Statute | 1 |
| `eo-13556.json` | EO 13556 | Executive order | 2 |
| `omb-a-130.json` | OMB Circular A-130 | OMB circular | 3 |
| `32-cfr-2002.json` | 32 CFR Part 2002 | Federal regulation | 4 |
| `fips-199.json` | FIPS 199 | FIPS | 5 |
| `fips-140-2.json` | FIPS 140-2 | FIPS | 5 |
| `fips-200.json` | FIPS 200 | FIPS | 5 |
| `nist-sp-800-53-r5.json` | NIST SP 800-53 Rev 5 | Standard | 6 |
| `nist-sp-800-171-r2.json` | NIST SP 800-171 Rev 2 | Standard | 6 |
| `nist-sp-800-88-r1.json` | NIST SP 800-88 Rev 1 | Standard | 6 |
| `nara-cui-registry.json` | NARA CUI Registry | Registry | 6 |
| `nara-cui-marking-hbk.json` | NARA CUI Marking Handbook | Handbook | 6 |
| `npd-2810-1f.json` | NPD 2810.1F | Agency policy | 7 |
| `npr-2810-7.json` | NPR 2810.7 | Agency procedure | 8 |
| `its-hbk-cui.json` | ITS-HBK-2810.09-02 | Handbook | 9 |

## Authority Graph

Each standard includes optional `authority` metadata describing:
- **`derives_from`** — vertical authority chain (legal basis)
- **`references`** — lateral cross-references

Generate visualizations with `python tools/authority-graph.py`. Validate graph integrity with `python tools/validate.py --graph`.

## Schema

All files conform to `schemas/standard.schema.json`.
