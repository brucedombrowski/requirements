# Curation Policy

How we decide what's in the catalog and at what depth.

## Two tiers of standards membership

Every entry in `standards/` is one of two tiers:

### Full standards
Fully captured: metadata, local source PDF, SHA-256, authority graph
edges, annotation file (`*.notes.json`) when known issues exist.
Reviewed and verified.

A standard is **full** if and only if a reviewer has:
- Read the source document end-to-end
- Verified the authority chain edges against the source
- Captured any known issues in an annotation file (or confirmed there
  are none worth recording)

### Stub standards
Minimal entry: `id`, `name`, `type`, `url`, `status: "stub"`. Exists so
that lateral references from full standards aren't dangling, but the
document hasn't been reviewed in depth.

Stubs deliberately omit `local_copy`, `sha256`, the `authority` block,
and any annotation file. They represent acknowledged scope without
implying review.

## Scope discipline

The risk this policy guards against: **transitive scope creep.** Every
NIST CSRC page lists "Laws and Regulations" and "Related NIST
Publications." Following every link breadth-first turns the catalog
into a bibliography of all federal infosec material — which collapses
curation quality and dilutes the focus on documents we actually use.

Rules:

1. **Scrapers produce stubs, never full standards.** When extracting
   metadata from a NIST CSRC page (or similar), any newly-discovered
   document goes in as a stub. Promotion to full is a separate,
   deliberate task.
2. **Promote stubs only when the work demands it.** If we start
   decomposing a document in `catalog/` whose authority chain depends
   on a stub, that stub gets promoted as part of the decomposition
   work. Otherwise it stays a stub indefinitely — that's fine.
3. **Validation tracks stub count separately.** `validate.py` reports
   the stub count alongside the full count so the curation backlog is
   always visible.
4. **Stubs don't get annotation files.** Annotations require review;
   stubs are by definition unreviewed.

## What ends up in the catalog at all

A document is eligible for stub-or-full entry in `standards/` if it
satisfies *any* of these:

- Appears in the authority chain (`derives_from`) of any existing
  full standard, or
- Appears in the lateral references (`references`) of any existing
  full standard, or
- Is named in the `Laws and Regulations` or `Related NIST
  Publications` section of an authoritative source-document landing
  page (e.g., NIST CSRC) for a full standard

Documents that don't meet any of these are out of scope, even if
relevant in some abstract sense.

## Why this matters

The value of the catalog grows with curation quality, not document
count. 30 well-reviewed standards beat 200 superficial ones — for
LLM grounding, for compliance use, for portfolio evidence, for any
purpose that depends on the catalog being trustworthy.
