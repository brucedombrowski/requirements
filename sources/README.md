# Source Documents

Local copies of every source document this catalog decomposes from. Every
file here is a US government work and therefore in the public domain
(17 USC § 105).

The point of keeping them in-repo is **clean-room provenance**: the
requirements in `catalog/` and the metadata in `standards/` are derived
from the exact bytes in this directory, not from a moving target on the
open internet. Each `standards/<id>.json` records the `local_copy` path
and a `sha256` digest so integrity can be verified at any time:

```bash
python tools/validate.py --sources
```

## Layout

```
sources/
├── nist/        # NIST publications (FIPS, SP 800-series)
├── nasa/        # NASA NPR / NPD agency directives
├── nara/        # NARA-published CUI guidance
└── federal/     # Constitution, US Code, Executive Orders, OMB, CFR
```

## Coverage

18 of the 20 standards in `standards/` have a local PDF copy. The two
exceptions:

| Standard | Reason |
|----------|--------|
| `ITS-HBK-CUI` | Source PDF is no longer publicly accessible (NASA-internal). The standard is referenced for authority-chain completeness only. |
| `NARA-CUI-Registry` | Live web database, not a single document. A structured snapshot is captured at `registries/nara-cui/registry.json`. |

## Refreshing a source

If a standard issues a new revision and you replace its PDF here:

1. Recompute the digest: `shasum -a 256 sources/<path>`
2. Update `local_copy`, `sha256`, and `date_accessed` in `standards/<id>.json`
3. Re-run `python tools/validate.py --sources` to confirm
