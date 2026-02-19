# Templates

Templates for consuming projects.

## Files

| Template | Purpose | Schema |
|----------|---------|--------|
| `project-selection.json` | Declare which catalog requirements your project adopts | `schemas/project-selection.schema.json` |
| `custom-requirement-set.json` | Create project-specific requirements not in the catalog | `schemas/requirement-set.schema.json` |

## Usage

1. Copy the appropriate template to your project
2. Fill in project metadata and selections
3. Validate with `python tools/validate.py your-file.json`
