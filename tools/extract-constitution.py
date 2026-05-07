#!/usr/bin/env python3
"""Deterministic extractor: NARA HTML transcripts -> structured JSON.

Reads three NARA-published HTML transcripts from sources/federal/us-constitution-html/
and emits a single catalog/federal/us-constitution/document.json with a
clean prose structure for LLM retrieval. The script is purely
mechanical — same HTML input always produces the same JSON output —
and records the source HTML SHA-256 digests in the output's `source`
block for byte-level provenance.

Usage:
    python tools/extract-constitution.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from lxml import html as lh

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "sources" / "federal" / "us-constitution-html"
OUT_PATH = REPO_ROOT / "catalog" / "federal" / "us-constitution" / "document.json"

ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII",
    9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII", 14: "XIV", 15: "XV",
    16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX", 20: "XX", 21: "XXI",
    22: "XXII", 23: "XXIII", 24: "XXIV", 25: "XXV", 26: "XXVI", 27: "XXVII",
}
ROMAN_TO_INT = {v: k for k, v in ROMAN.items()}

# Ratification dates from NARA's published record. Static fact, not parsed.
AMENDMENT_DATES = {
    "I": "1791-12-15", "II": "1791-12-15", "III": "1791-12-15", "IV": "1791-12-15",
    "V": "1791-12-15", "VI": "1791-12-15", "VII": "1791-12-15", "VIII": "1791-12-15",
    "IX": "1791-12-15", "X": "1791-12-15",
    "XI": "1795-02-07", "XII": "1804-06-15", "XIII": "1865-12-06",
    "XIV": "1868-07-09", "XV": "1870-02-03", "XVI": "1913-02-03",
    "XVII": "1913-04-08", "XVIII": "1919-01-16", "XIX": "1920-08-18",
    "XX": "1933-01-23", "XXI": "1933-12-05", "XXII": "1951-02-27",
    "XXIII": "1961-03-29", "XXIV": "1964-01-23", "XXV": "1967-02-10",
    "XXVI": "1971-07-01", "XXVII": "1992-05-07",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def text_of(elem) -> str:
    """Concatenated text content of an lxml element, normalized."""
    if elem is None:
        return ""
    return normalize("".join(elem.itertext()))


def find_main_content(doc):
    """Find the article content container in NARA's page template."""
    # NARA uses `<div id="content-area">...` or `<article>...`.
    for xpath in ('//*[@id="content-area"]', '//article', '//main', '//div[@role="main"]'):
        nodes = doc.xpath(xpath)
        if nodes:
            return nodes[0]
    return doc


def collect_text_until_next_heading(start_elem, stop_tags, stop_attrs_predicate=None):
    """Walk siblings forward from start_elem, gathering text from <p> until a stop element."""
    chunks = []
    for sib in start_elem.itersiblings():
        if sib.tag in stop_tags:
            if stop_attrs_predicate is None or stop_attrs_predicate(sib):
                break
        if sib.tag == "p":
            t = text_of(sib)
            if t:
                chunks.append(t)
    return chunks


def extract_articles(html_path: Path):
    """Parse the Articles I–VII transcript page into preamble + articles list."""
    with open(html_path, "rb") as f:
        doc = lh.parse(f).getroot()
    body = find_main_content(doc)

    # Preamble: text between page H1 and the first Article. NARA's transcript
    # uses an <h2 id="1">Article. I.</h2> for the first article boundary.
    preamble_paras = []
    article_h2s = body.xpath('.//h2[@id="1" or @id="2" or @id="3" or @id="4" or @id="5" or @id="6" or @id="7"]')
    if not article_h2s:
        raise SystemExit(f"No <h2 id='N'>Article</h2> markers found in {html_path}")
    first_article = article_h2s[0]

    # Collect <p> text strictly before the first article H2 (within the body container).
    for p in body.iter("p"):
        if first_article in (p,) or any(p is anc for anc in first_article.iterancestors()):
            continue
        # Stop once we hit / pass the first article in document order.
        if p.sourceline and first_article.sourceline and p.sourceline >= first_article.sourceline:
            break
        t = text_of(p)
        if t:
            preamble_paras.append(t)

    # Heuristic: the preamble paragraph starts with "We the People".
    preamble = next((p for p in preamble_paras if p.lower().startswith("we the people")), None)
    if preamble is None and preamble_paras:
        # Fallback: longest paragraph before the first article.
        preamble = max(preamble_paras, key=len)

    # Articles + sections
    articles = []
    for a_idx, a_h2 in enumerate(article_h2s):
        article_num_int = int(a_h2.get("id"))
        article_num = ROMAN[article_num_int]
        # Sections within this article: <h3 id="N-M">
        next_a_line = article_h2s[a_idx + 1].sourceline if a_idx + 1 < len(article_h2s) else None
        section_h3s = body.xpath(f'.//h3[starts-with(@id, "{article_num_int}-")]')
        sections = []
        for s_idx, s_h3 in enumerate(section_h3s):
            sec_id = s_h3.get("id")
            sec_num = sec_id.split("-", 1)[1]
            # Collect <p> elements between this section and the next heading.
            next_h3_line = section_h3s[s_idx + 1].sourceline if s_idx + 1 < len(section_h3s) else next_a_line
            paras = []
            for p in body.iter("p"):
                if not p.sourceline:
                    continue
                if p.sourceline <= s_h3.sourceline:
                    continue
                if next_h3_line and p.sourceline >= next_h3_line:
                    break
                t = text_of(p)
                if t:
                    paras.append(t)
            sections.append({"number": sec_num, "text": " ".join(paras)})
        articles.append({"number": article_num, "sections": sections})

    return preamble, articles


def extract_amendments_1_to_10(html_path: Path):
    """Parse the Bill of Rights transcript page into amendments I–X."""
    with open(html_path, "rb") as f:
        doc = lh.parse(f).getroot()
    body = find_main_content(doc)

    h3s = body.xpath('.//h3')
    amendment_h3s = [h for h in h3s if re.match(r"^Amendment\s+[IVX]+$", text_of(h) or "")]
    if not amendment_h3s:
        raise SystemExit(f"No Amendment headings found in {html_path}")

    amendments = []
    for i, h in enumerate(amendment_h3s):
        roman = text_of(h).split()[1]
        next_line = amendment_h3s[i + 1].sourceline if i + 1 < len(amendment_h3s) else None
        paras = []
        for p in body.iter("p"):
            if not p.sourceline or p.sourceline <= h.sourceline:
                continue
            if next_line and p.sourceline >= next_line:
                break
            t = text_of(p)
            if t:
                paras.append(t)
        amendments.append({
            "number": roman,
            "ratified": AMENDMENT_DATES.get(roman, ""),
            "text": " ".join(paras),
        })
    return amendments


def extract_amendments_11_to_27(html_path: Path):
    """Parse the Amendments XI–XXVII page (anchor-based markup)."""
    with open(html_path, "rb") as f:
        doc = lh.parse(f).getroot()
    body = find_main_content(doc)

    # Each amendment is preceded by an <a id="xi">, <a id="xii">, etc. (lowercase Roman).
    anchors = body.xpath('.//a[@id]')
    amend_anchors = []
    for a in anchors:
        aid = a.get("id", "")
        # Match top-level Roman ids (xi, xii, xiii, ... xxvii) but not section variants
        # like xiii1, xiv2 (which carry trailing digits).
        m = re.match(r"^([ivxlcdm]+)$", aid)
        if not m:
            continue
        upper = aid.upper()
        if upper in ROMAN_TO_INT and 11 <= ROMAN_TO_INT[upper] <= 27:
            amend_anchors.append((upper, a))

    # Sub-section anchors: e.g. xiii1, xiv2 etc.
    section_anchors_by_amend = {}
    for a in anchors:
        aid = a.get("id", "")
        m = re.match(r"^([ivxlcdm]+)(\d+)$", aid)
        if not m:
            continue
        upper = m.group(1).upper()
        if upper not in ROMAN_TO_INT:
            continue
        section_anchors_by_amend.setdefault(upper, []).append((m.group(2), a))

    amendments = []
    for i, (roman, anchor) in enumerate(amend_anchors):
        next_line = amend_anchors[i + 1][1].sourceline if i + 1 < len(amend_anchors) else None
        sec_anchors = sorted(section_anchors_by_amend.get(roman, []), key=lambda x: int(x[0]))

        if sec_anchors:
            sections = []
            for j, (sec_num, sec_anchor) in enumerate(sec_anchors):
                sec_next = sec_anchors[j + 1][1].sourceline if j + 1 < len(sec_anchors) else next_line
                paras = []
                for p in body.iter("p"):
                    if not p.sourceline or p.sourceline <= sec_anchor.sourceline:
                        continue
                    if sec_next and p.sourceline >= sec_next:
                        break
                    t = text_of(p)
                    if t:
                        paras.append(t)
                sections.append({"number": sec_num, "text": " ".join(paras)})
            amendments.append({
                "number": roman,
                "ratified": AMENDMENT_DATES.get(roman, ""),
                "sections": sections,
            })
        else:
            paras = []
            for p in body.iter("p"):
                if not p.sourceline or p.sourceline <= anchor.sourceline:
                    continue
                if next_line and p.sourceline >= next_line:
                    break
                t = text_of(p)
                if t:
                    paras.append(t)
            amendments.append({
                "number": roman,
                "ratified": AMENDMENT_DATES.get(roman, ""),
                "text": " ".join(paras),
            })
    return amendments


def main() -> int:
    articles_html = SOURCE_DIR / "articles.html"
    bor_html = SOURCE_DIR / "bill-of-rights.html"
    amend_html = SOURCE_DIR / "amendments-11-27.html"

    for p in (articles_html, bor_html, amend_html):
        if not p.exists():
            raise SystemExit(f"Missing source: {p}")

    preamble, articles = extract_articles(articles_html)
    amendments_1_10 = extract_amendments_1_to_10(bor_html)
    amendments_11_27 = extract_amendments_11_to_27(amend_html)
    amendments = amendments_1_10 + amendments_11_27

    if len(amendments) != 27:
        print(
            f"WARNING: extracted {len(amendments)} amendments (expected 27)",
            file=sys.stderr,
        )

    out = {
        "document_info": {
            "id": "USC-CONST",
            "title": "The Constitution of the United States",
            "short_name": "U.S. Constitution",
            "type": "constitutional_provision",
            "issuing_organization": "United States Government",
            "ratified_date": "1788-06-21",
            "articles_count": len(articles),
            "amendments_count": len(amendments),
        },
        "source": {
            "extracted_from": [
                {
                    "path": str(p.relative_to(REPO_ROOT)),
                    "url": url,
                    "sha256": sha256_file(p),
                }
                for p, url in [
                    (articles_html, "https://www.archives.gov/founding-docs/constitution-transcript"),
                    (bor_html, "https://www.archives.gov/founding-docs/bill-of-rights-transcript"),
                    (amend_html, "https://www.archives.gov/founding-docs/amendments-11-27"),
                ]
            ],
            "generator": "tools/extract-constitution.py",
            "generated_at": dt.date.today().isoformat(),
        },
        "preamble": preamble or "",
        "articles": articles,
        "amendments": amendments,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(articles)} articles, {len(amendments)} amendments, "
          f"{len(out.get('preamble',''))} chars of preamble")
    return 0


if __name__ == "__main__":
    sys.exit(main())
