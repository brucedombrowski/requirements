# Lessons Learned

Notes captured while building this catalog. The point: AI-assisted
regulatory compliance work needs trusted source data, and source data
is messier than people assume. The methodology in this repo
(deterministic extraction + byte-pinned sources + cross-verification)
handles that messiness; this document records the specific failure
modes we ran into so future contributors don't have to relearn them.

## Source data is not as authoritative as it looks

### Stale cross-references in active U.S. law

`40 U.S.C. § 11331` defines "information security" by reference to
`44 U.S.C. § 3542(b)(1)` — but § 3542 was repealed in 2014 by the
FISMA Modernization Act (P.L. 113-283). The substantive content
moved to `44 U.S.C. § 3552(b)(1)`, but Congress's conforming
amendments missed § 11331's cross-reference. The link in the
official OLRC editorial note still points at the dead section a
decade later.

**Implication.** Even active federal statutes contain dead
references. AI assistants relying on USC text without provenance
can confidently cite a section that no longer exists. To fix:
contact the Office of the Law Revision Counsel
([uscode.help@mail.house.gov](mailto:uscode.help@mail.house.gov))
for editorial-note corrections; substantive statutory fixes need a
Member of Congress and a technical-corrections bill.

### Source URLs decay silently

The canonical URL for NASA's `ITS-HBK-2810.09-02` (NASA CUI
Handbook) returns `404`. The Wayback Machine has no snapshots —
likely the document was never publicly hosted at that URL despite
being cited as the canonical pointer for years. We redirected the
catalog entry to the parent NPR's NODIS page rather than dropping
the standard, since the authority chain still needs the handbook
tier.

NASA NODIS itself has bizarre URL conventions: "View all pages in
PDF" is a JavaScript redirect to `/npg_img/<ID>/<ID>.pdf` rather
than a direct link, and the OPD listings don't always include all
available documents.

**Implication.** Any compliance tooling that lazily fetches by URL
will silently break. Local copies + `sha256` verification are the
only defense.

### "Authoritative" sources have known bugs and gaps

- **No canonical machine-readable Constitution.** OLRC publishes
  USC titles in USLM XML — but not the Constitution itself. CONAN
  (Constitution Annotated) is a ~33 MB XML file dominated by
  judicial analysis, not pure text. NARA's HTML transcripts are the
  most authoritative pure-text form, and they're three separate
  pages with three different markup conventions.
- **NIST OSCAL coverage is partial.** Official OSCAL JSON exists
  for SP 800-53 Rev 5 and SP 800-171 Rev 3 — but **not** Rev 2.
  Since DoD CMMC 2.0 and most existing federal contracts still
  anchor on Rev 2, the Rev 2 catalog has to be hand-extracted,
  with that scope caveat documented inline.
- **Other people's JSON has silent omissions.** A widely-referenced
  GitHub Constitution-as-JSON repository is missing Article VII
  entirely. Hand-curated data tends to lose pieces without anyone
  noticing.

**Implication.** Mechanical extraction from a fixed authoritative
source, repeated by anyone with the same input, beats trusting a
"clean" pre-published JSON.

## Extraction methodology

### Two independent parsers catch what one misses

When extracting the Constitution from NARA HTML, the production
extractor (`lxml`-based, uses XPath and `sourceline` ranges) was
spot-checked against an independent regex-based verifier I wrote
just for the comparison. The two implementations disagreed on
three passages — every disagreement was a real bug:

1. `<p class="smaller">` editorial notes ("Originally proposed
   Sept. 25, 1789. Ratified May 7, 1992.") leaking into amendment
   text.
2. The last amendment in each NARA page picking up sidebar /
   footer / "Back to Constitution Main Page" navigation
   paragraphs.
3. Article VII dropping `<strong>` state-name labels from the
   signers section.

After the fixes, both parsers agree byte-for-byte on all 7
articles and all 10 Bill of Rights amendments. Without the
second parser, none of these would have surfaced.

**Implication.** For any non-trivial extraction, write a
verification path that uses different code than the production
extractor. Disagreement means a bug; agreement means the source
is faithfully captured.

### Source-document chrome looks like document text

NARA's transcripts mix the actual constitutional text with
editorial paragraphs that *look* identical structurally:

- Ratification notes (`<p class="smaller">`)
- Navigation buttons (`<p>` containing only `<a class="btn">`)
- Cross-reference prose ("For biographies of the non-signing
  delegates...see the Founding Fathers page") — distinguishable
  from the signers list (also `/founding-docs/` links!) only by
  the presence of plain text *outside* the links
- Sidebar / footer paragraphs that share the same outer container

A naïve "all `<p>` text" extractor will silently include all of
this. The fix: precise filters based on element class, child
structure, link href, and *positional* text outside link content.

### Deterministic regen as a drift signal

Every machine-derived artifact in this repo carries a `source`
block recording the upstream artifact's path and SHA-256:

- `controls/nist-800-53/catalog.json` ← `sources/nist/oscal/...`
- `controls/nist-800-171/rev3/catalog.json` ← `sources/nist/oscal/...`
- `catalog/federal/us-constitution/constitution.json` ← three NARA HTML
  files

Re-running the corresponding tool against unchanged input produces
byte-identical output. Any future diff in the derived JSON is a
direct signal that the upstream changed — no surveillance script
required, no "did NIST update this" queries.

## Format choices

### Authoritative XML/OSCAL as source, prose-structured JSON for retrieval

The instinct to use authoritative XML (USLM, OSCAL) directly is
right *as a source-of-truth* — it's tagged, stable, and
government-published. But for direct LLM retrieval, XML is
awkward:

- Tag soup inflates token counts ~6× over equivalent prose
- Modern LLM tokenizers (BPE on web text) don't have efficient
  tokens for `<` / `</`; each tag eats 3–5 tokens
- Retrieval similarity favors prose because LLMs see vastly more
  prose than tag-rich content during pretraining
- RAG chunkers expect natural prose breaks, not nested tag trees

The pattern this repo uses: keep the authoritative format as the
in-repo source of truth, and *deterministically* derive prose-
structured JSON for retrieval. Same source, two consumers, one
reproducible pipeline.

### GitHub strips SVG interactivity in READMEs

A graph rendered as SVG with embedded `<a xlink:href>` annotations
is fully clickable in a browser — but GitHub renders SVGs in
README markdown and in its blob viewer as `<img>` tags, which
strips all interactivity. Two paths that actually work:

- Generate a clickable PDF from the SVG (`rsvg-convert -f pdf`).
  PDF link annotations survive into any PDF viewer; users can
  click nodes in Preview/Adobe/browser PDF.
- Host an HTML page via GitHub Pages that embeds the SVG via
  `<object>`. Live and interactive but adds Pages setup overhead.

This repo uses the PDF route — the README image links to
`docs/authority-graph.pdf` which works offline and in any viewer.

## What this means for AI-assisted clean-room compliance work

The repo could plausibly look "clean" to an outside reviewer
right now — single MIT license, validation passes, deterministic
extractors, authority graph renders. But the pieces that *make*
it clean were exactly the failure modes documented above:

- Without `--sources` SHA-256 verification, the broken NASA URL
  would have looked fine until somebody actually clicked it
- Without a second parser, our Constitution extractor would have
  shipped with three silent text bugs
- Without explicit handling of OSCAL coverage gaps, the 800-171
  Rev 2 catalog would have looked like a complete mechanical
  extraction (it's not — it's a hand-extracted starter)
- Without distinguishing editorial chrome from document text,
  the LLM corpus would include "Originally proposed Sept. 25,
  1789. Ratified May 7, 1992." as if it were part of Amendment
  XXVII's binding text

For an air-gapped local-LLM compliance assistant grounded in this
corpus, every one of those bugs would have produced wrong answers
with confident-looking citations. The methodology — not the model
— is what makes the system trustworthy.
