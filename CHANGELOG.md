# Changelog

All notable changes to the requirements catalog are documented here.

## [1.0.0] - 2026-02-19

### Added
- Initial repository structure with JSON schemas (draft-2020-12)
- 4 schemas: requirement-set, standard, control, project-selection
- 8 standard definitions (NIST SP 800-53, 800-171, 800-88, FIPS 199, FIPS 140-2, EO 13556, 32 CFR 2002, NARA CUI Registry)
- NASA NPR 2810.7 requirements (72 requirements, Active)
- NASA NID 2810.135 requirements (72 requirements, Expired — test data)
- NIST 800-53 control catalog (14 controls, definition-only)
- NIST 800-171 control catalog (11 controls, definition-only)
- Project selection and custom requirement set templates
- `validate.py` tool for JSON schema validation
- README documentation at all directory levels

### Migration Sources
- `catalog/nasa/npr-2810-7/` from LaTeX `REQ-2026-003_npr_2810_7_cui.json`
- `catalog/nasa/nid-2810-135/` from LaTeX `REQ-2026-002_nid_2810_135_cui.json`
- `controls/nist-800-53/` from Security `controls/nist-800-53.json` (implementation blocks stripped)
- `controls/nist-800-171/` from Security `controls/nist-800-171.json` (implementation blocks stripped)
