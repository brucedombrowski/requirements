# U.S. Constitution

Structured JSON representation of the Constitution of the United States,
extracted deterministically from NARA's published transcripts.

## Files

- `document.json` — preamble + 7 articles (with sections) + 27 amendments
  (with sections where the amendment is split). Each section is a clean
  prose chunk suitable for LLM retrieval; each amendment carries its
  ratification date.

## Provenance

Generated from three NARA transcripts under
`sources/federal/us-constitution-html/`:

| File | NARA URL |
|------|----------|
| `articles.html` | <https://www.archives.gov/founding-docs/constitution-transcript> |
| `bill-of-rights.html` | <https://www.archives.gov/founding-docs/bill-of-rights-transcript> |
| `amendments-11-27.html` | <https://www.archives.gov/founding-docs/amendments-11-27> |

The `source.extracted_from` block in `document.json` records each HTML
file's path, URL, and SHA-256. NARA is the legal custodian of the
Constitution (the original parchment is in their vault), so these
transcripts are the closest thing to a "canonical" plain text.

## Regeneration

If a NARA transcript changes (e.g., NARA fixes a typo) or one of the
HTML files is replaced:

```bash
python tools/extract-constitution.py
python tools/validate.py
```

Re-running produces byte-identical output for a given input. Diffs in
`document.json` after regeneration imply the underlying NARA HTML
changed — review before committing.

## Citation

> "Constitution of the United States: A Transcription." *National
> Archives*, U.S. National Archives and Records Administration.
> Accessed 7 May 2026.
> <https://www.archives.gov/founding-docs/constitution-transcript>.
