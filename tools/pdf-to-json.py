#!/usr/bin/env python3
"""
Extract structured JSON from NASA procedural requirement PDFs.

Converts PDF documents (NPR, NID, NPD) into structured JSON capturing
every piece of text, organized by section hierarchy. No AI dependency.

Usage:
    python tools/pdf-to-json.py INPUT.pdf OUTPUT.json
    python tools/pdf-to-json.py INPUT.pdf                   # writes to stdout
    python tools/pdf-to-json.py INPUT.pdf -o OUTPUT.json

Dependencies:
    pip install pdfplumber
"""

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber is required. Install with: pip install pdfplumber", file=sys.stderr)
    sys.exit(1)


# --- Section header patterns ---
# Matches: "P.1 Purpose", "1.1 Overview", "2.13 Safeguarding and Storage"
SECTION_HEADER_RE = re.compile(
    r'^(?:Chapter\s+)?(\d+(?:\.\d+)*)\s+(.+)$'
)
# Matches: "P.1", "P.2", etc.
PREFACE_SECTION_RE = re.compile(r'^P\.(\d+)\s+(.+)$')
# Matches: "Appendix A. Definitions", "Appendix B Acronyms"
APPENDIX_RE = re.compile(r'^Appendix\s+([A-Z])\.?\s+(.+)$')
# Matches numbered paragraphs: "1.1.1", "2.13.4", "1.2.3"
PARAGRAPH_NUM_RE = re.compile(r'^(\d+(?:\.\d+)+)\s+(.+)$')
# Matches lettered sub-items: "a. text", "b. text"
SUB_ITEM_RE = re.compile(r'^([a-z])\.?\s+(.+)$')
# Matches numbered sub-sub items: "(1) text", "(2) text"
SUB_SUB_ITEM_RE = re.compile(r'^\((\d+)\)\s+(.+)$')
# Matches Appendix C matrix section headers: "C.1 Authorized Holders"
MATRIX_SECTION_RE = re.compile(r'^C\.(\d+)\s+(.+)$')
# Matches Appendix D entries: "D.1 CUI Registry Website: URL"
WEB_RESOURCE_RE = re.compile(r'^D\.(\d+)\s+(.+)$')
# Matches change history table header
CHANGE_HISTORY_RE = re.compile(r'CHANGE\s+HISTORY', re.IGNORECASE)
# Bold definition terms (Appendix A pattern)
DEFINITION_TERM_RE = re.compile(r'^([A-Z][A-Za-z\s,()]+?)(?:\s+is\s+|\s+are\s+|\s+occurs?\s+)')
# Matches italic notes
NOTE_RE = re.compile(r'^Note:\s*(.+)$', re.IGNORECASE)


def extract_text_by_page(pdf_path):
    """Extract text from each page of a PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Extract tables separately
            tables = page.extract_tables() or []
            pages.append({
                "page_number": page.page_number,
                "text": text,
                "tables": tables,
            })
    return pages


def strip_page_headers_footers(text, doc_id="NPR 2810.7"):
    """Remove page headers, footers, and boilerplate from extracted text."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip page headers like "NPR 2810.7 -- Chapter2 Page 20 of 42"
        if re.match(r'^NPR\s+2810\.7\s+--', stripped):
            continue
        # Skip page numbers
        if re.match(r'^Page\s+\d+\s+of\s+\d+', stripped):
            continue
        # Skip the standard footer disclaimer
        if 'This document does not bind the public' in stripped:
            continue
        if 'incorporated into a contract' in stripped:
            continue
        if 'NASA Online Directives Information System' in stripped:
            continue
        if 'this is the correct version before use' in stripped:
            continue
        if stripped.startswith('| NODIS Library |'):
            continue
        if stripped == doc_id:
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()


def detect_document_info(pages):
    """Extract document metadata from the first page."""
    first_page = pages[0]["text"] if pages else ""

    info = {
        "id": "",
        "title": "",
        "responsible_office": "",
        "effective_date": "",
        "expiration_date": "",
        "compliance": "",
        "pages": len(pages),
    }

    # Extract NPR number
    m = re.search(r'(NPR|NID|NPD)\s+([\d.]+)', first_page)
    if m:
        info["id"] = f"{m.group(1)} {m.group(2)}"

    # Extract dates
    m = re.search(r'Effective Date:\s*(.+?)(?:\n|$)', first_page)
    if m:
        info["effective_date"] = m.group(1).strip()

    m = re.search(r'Expiration Date:\s*(.+?)(?:\n|$)', first_page)
    if m:
        info["expiration_date"] = m.group(1).strip()

    # Extract title - usually the first bold/large line after header
    for line in first_page.split('\n'):
        line = line.strip()
        if line.startswith('Controlled Unclassified') or line.startswith('CUI'):
            info["title"] = line
            break

    # Responsible office
    m = re.search(r'Responsible Office:\s*(.+?)(?:\n|$)', first_page)
    if m:
        info["responsible_office"] = m.group(1).strip()

    # Compliance
    if 'COMPLIANCE IS MANDATORY' in first_page:
        m = re.search(r'COMPLIANCE IS MANDATORY.+', first_page)
        if m:
            info["compliance"] = m.group(0).strip()

    return info


def parse_change_history(pages):
    """Extract change history table from the document."""
    changes = []
    for page_data in pages:
        if page_data["tables"]:
            for table in page_data["tables"]:
                # Check if this looks like a change history table
                if table and len(table) > 0:
                    header = table[0] if table[0] else []
                    header_text = ' '.join(str(c) for c in header if c).lower()
                    if 'chg' in header_text or 'change' in header_text:
                        for row in table[1:]:
                            if row and any(row):
                                change = {
                                    "change_number": str(row[0]).strip() if row[0] else "",
                                    "date": str(row[1]).strip() if len(row) > 1 and row[1] else "",
                                    "description": str(row[2]).strip() if len(row) > 2 and row[2] else "",
                                }
                                if change["change_number"]:
                                    changes.append(change)
        # Also check text-based change history
        text = page_data["text"]
        if CHANGE_HISTORY_RE.search(text):
            # Try to parse from text if tables didn't work
            if not changes:
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.match(r'^\d+\s+\d{2}/\d{2}/\d{4}', line.strip()):
                        parts = line.strip().split(None, 2)
                        if len(parts) >= 3:
                            changes.append({
                                "change_number": parts[0],
                                "date": parts[1],
                                "description": parts[2],
                            })
    return changes


def classify_page_section(text):
    """Determine which section a page belongs to based on its header."""
    first_line = text.split('\n')[0].strip() if text else ""

    if 'TOC' in first_line:
        return 'toc'
    if 'ChangeHistory' in first_line or 'CHANGE HISTORY' in text[:200]:
        return 'change_history'
    if 'Preface' in first_line:
        return 'preface'
    if 'Chapter1' in first_line or 'Chapter 1' in text[:100]:
        return 'chapter1'
    if 'Chapter2' in first_line or 'Chapter 2' in text[:100]:
        return 'chapter2'
    if 'AppendixA' in first_line:
        return 'appendix_a'
    if 'AppendixB' in first_line:
        return 'appendix_b'
    if 'AppendixC' in first_line:
        return 'appendix_c'
    if 'AppendixD' in first_line:
        return 'appendix_d'
    return 'unknown'


def parse_preface_sections(text):
    """Parse preface text into structured sections P.1 through P.6."""
    sections = OrderedDict()
    current_section = None
    current_paragraphs = []

    lines = text.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for preface section header
        m = PREFACE_SECTION_RE.match(stripped)
        if m:
            if current_section:
                sections[current_section["id"]] = current_section
                current_section["paragraphs"] = current_paragraphs
            current_section = {
                "id": f"P.{m.group(1)}",
                "title": m.group(2),
                "paragraphs": [],
            }
            current_paragraphs = []
            continue

        # Check for major headers to skip
        if stripped in ('Preface',):
            continue

        if current_section:
            # Detect lettered paragraphs: "a. text", "b. text"
            sub_m = SUB_ITEM_RE.match(stripped)
            if sub_m:
                para_id = f"{current_section['id']}.{sub_m.group(1)}"
                current_paragraphs.append({
                    "id": para_id,
                    "text": sub_m.group(2),
                })
            else:
                # Check for numbered sub-items: "(1) text"
                sub_sub_m = SUB_SUB_ITEM_RE.match(stripped)
                if sub_sub_m:
                    current_paragraphs.append({
                        "id": f"({sub_sub_m.group(1)})",
                        "text": sub_sub_m.group(2),
                    })
                else:
                    # Continuation text or standalone paragraph
                    if current_paragraphs and not stripped[0].isupper():
                        # Continuation of previous paragraph
                        current_paragraphs[-1]["text"] += " " + stripped
                    else:
                        current_paragraphs.append({
                            "id": "",
                            "text": stripped,
                        })

    if current_section:
        current_section["paragraphs"] = current_paragraphs
        sections[current_section["id"]] = current_section

    return sections


def parse_chapter_text(text):
    """Parse chapter text into sections and paragraphs."""
    sections = OrderedDict()
    current_section_id = None
    current_section_title = None
    current_paragraphs = []

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        # Skip chapter headers
        if stripped.startswith('Chapter '):
            i += 1
            continue

        # Check for section header (e.g., "2.1 General", "1.1 Overview")
        # Section headers are typically short lines with a number and title
        m = re.match(r'^(\d+\.\d+)\s+(.+)$', stripped)
        if m and len(stripped) < 80 and not re.match(r'^\d+\.\d+\.\d+', stripped):
            # Save previous section
            if current_section_id:
                sections[current_section_id] = {
                    "title": current_section_title,
                    "paragraphs": current_paragraphs,
                }
            current_section_id = m.group(1)
            current_section_title = m.group(2)
            current_paragraphs = []
            i += 1
            continue

        # Check for numbered paragraph (e.g., "2.1.1", "1.2.3")
        p_m = PARAGRAPH_NUM_RE.match(stripped)
        if p_m:
            current_paragraphs.append({
                "id": p_m.group(1),
                "text": p_m.group(2),
            })
            i += 1
            continue

        # Check for lettered sub-item
        sub_m = SUB_ITEM_RE.match(stripped)
        if sub_m:
            para_id = sub_m.group(1)
            current_paragraphs.append({
                "id": para_id,
                "text": sub_m.group(2),
            })
            i += 1
            continue

        # Check for numbered sub-sub items: "(1) text"
        sub_sub_m = SUB_SUB_ITEM_RE.match(stripped)
        if sub_sub_m:
            current_paragraphs.append({
                "id": f"({sub_sub_m.group(1)})",
                "text": sub_sub_m.group(2),
            })
            i += 1
            continue

        # Check for notes (italic)
        note_m = NOTE_RE.match(stripped)
        if note_m:
            current_paragraphs.append({
                "id": "note",
                "text": stripped,
                "type": "note",
            })
            i += 1
            continue

        # Continuation of previous paragraph or standalone text
        if current_paragraphs:
            last = current_paragraphs[-1]
            # If previous line ended mid-sentence, append
            if last["text"] and not last["text"].endswith('.') and not last["text"].endswith(':'):
                last["text"] += " " + stripped
            else:
                current_paragraphs.append({
                    "id": "",
                    "text": stripped,
                })
        else:
            current_paragraphs.append({
                "id": "",
                "text": stripped,
            })

        i += 1

    # Save last section
    if current_section_id:
        sections[current_section_id] = {
            "title": current_section_title,
            "paragraphs": current_paragraphs,
        }

    return sections


def parse_definitions(text):
    """Parse Appendix A definitions into a dictionary."""
    definitions = OrderedDict()
    lines = text.split('\n')
    current_term = None
    current_def = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ('Appendix A Definitions', 'Appendix A. Definitions'):
            continue

        # Definitions start with a bold term followed by "is", "are", "occurs"
        # In extracted text, bold terms appear at the start of a line
        # Try to detect term boundaries
        m = re.match(r'^([A-Z][A-Za-z\s,()]+?)\s+(is\s+|are\s+|occurs?\s+|of\s+CUI\s+)', stripped)
        if m and len(m.group(1).strip()) > 2:
            # Save previous definition
            if current_term:
                definitions[current_term] = ' '.join(current_def)
            current_term = m.group(1).strip()
            current_def = [stripped[len(current_term):].strip()]
        elif current_term:
            current_def.append(stripped)
        else:
            # Try alternate pattern: term followed by definition on same line
            # Some definitions don't start with "is/are"
            if re.match(r'^[A-Z]', stripped) and not re.match(r'^\d', stripped):
                if current_term:
                    definitions[current_term] = ' '.join(current_def)
                # Split at first "is" or "are"
                parts = re.split(r'\s+(is\s+|are\s+)', stripped, 1)
                if len(parts) >= 3:
                    current_term = parts[0].strip()
                    current_def = [parts[1] + parts[2]]
                else:
                    current_term = stripped
                    current_def = []

    if current_term:
        definitions[current_term] = ' '.join(current_def)

    return definitions


def parse_acronyms(text):
    """Parse Appendix B acronyms into a dictionary."""
    acronyms = OrderedDict()
    lines = text.split('\n')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('Appendix B'):
            continue

        # Acronym lines: "CDO Chief Data Officer"
        # Split on 2+ spaces, tab, or first transition from uppercase/punctuation to uppercase word
        parts = re.split(r'\s{2,}|\t', stripped, maxsplit=1)
        if len(parts) == 2:
            acronym = parts[0].strip()
            expansion = parts[1].strip()
            if acronym and expansion and re.match(r'^[A-Z]', acronym):
                acronyms[acronym] = expansion
        elif len(parts) == 1:
            # Try splitting on first space after an all-caps/punctuation token
            m = re.match(r'^([A-Z][A-Z0-9.\-\[\]() ]*?)\s{1,}([A-Z][a-z].+)$', stripped)
            if m:
                acronym = m.group(1).strip()
                expansion = m.group(2).strip()
                if len(acronym) <= 15:
                    acronyms[acronym] = expansion

    return acronyms


def parse_requirements_matrices_from_pages(pages):
    """Parse Appendix C requirements matrices from raw page data.

    Process pages sequentially so table rows get associated with the
    correct C.x section header that precedes them in the text.
    """
    matrices = OrderedDict()
    current_matrix_id = None
    current_matrix_title = None
    current_requirements = []

    for page_data in pages:
        text = strip_page_headers_footers(page_data["text"])
        tables = page_data.get("tables", [])

        # Scan text for C.x section headers
        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            m = MATRIX_SECTION_RE.match(stripped)
            if m:
                # Save previous matrix
                if current_matrix_id and current_requirements:
                    matrices[current_matrix_id] = {
                        "title": current_matrix_title,
                        "requirements": current_requirements,
                    }
                current_matrix_id = f"C.{m.group(1)}"
                current_matrix_title = m.group(2)
                current_requirements = []

        # Extract table rows from this page
        for table in tables:
            if table and len(table) > 0:
                for row in table:
                    if not row or not any(row):
                        continue
                    cell0 = str(row[0]).strip() if row[0] else ""
                    cell1 = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                    # Skip header rows
                    if cell0.lower().startswith('para') or cell0.lower() == '#':
                        continue
                    if cell0 and cell1:
                        # Clean up newlines in requirement text
                        cell1 = re.sub(r'\n', ' ', cell1)
                        current_requirements.append({
                            "para": cell0,
                            "text": cell1,
                        })

    # Save last matrix
    if current_matrix_id and current_requirements:
        matrices[current_matrix_id] = {
            "title": current_matrix_title,
            "requirements": current_requirements,
        }

    return matrices


def parse_web_resources(text):
    """Parse Appendix D web resources."""
    resources = []
    lines = text.split('\n')

    current_entry = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('Appendix D'):
            continue

        m = WEB_RESOURCE_RE.match(stripped)
        if m:
            if current_entry:
                resources.append(current_entry)
            entry_id = f"D.{m.group(1)}"
            rest = m.group(2)
            # Try to split description from URL
            url_m = re.search(r'(https?://\S+)', rest)
            if url_m:
                desc = rest[:url_m.start()].rstrip(': ')
                url = url_m.group(1)
                current_entry = {
                    "id": entry_id,
                    "description": desc,
                    "url": url,
                }
            else:
                current_entry = {
                    "id": entry_id,
                    "description": rest,
                    "url": "",
                }
        elif current_entry and stripped.startswith('http'):
            current_entry["url"] = stripped
        elif current_entry:
            # Continuation of description
            url_m = re.search(r'(https?://\S+)', stripped)
            if url_m:
                current_entry["url"] = url_m.group(1)
            else:
                current_entry["description"] += " " + stripped

    if current_entry:
        resources.append(current_entry)

    return resources


def pdf_to_json(pdf_path):
    """Main conversion: PDF -> structured JSON document."""
    pages = extract_text_by_page(pdf_path)

    # Classify pages by section
    section_pages = {}
    for page_data in pages:
        text = page_data["text"]
        section = classify_page_section(text)
        if section not in section_pages:
            section_pages[section] = []
        section_pages[section].append(page_data)

    # Extract document info
    doc_info = detect_document_info(pages)

    # Extract change history
    change_history = []
    if 'change_history' in section_pages:
        ch_text = '\n'.join(p["text"] for p in section_pages['change_history'])
        ch_tables = []
        for p in section_pages['change_history']:
            ch_tables.extend(p["tables"])
        change_history = parse_change_history(section_pages['change_history'])

    # Parse preface
    preface = {}
    if 'preface' in section_pages:
        preface_text = '\n'.join(
            strip_page_headers_footers(p["text"]) for p in section_pages['preface']
        )
        preface = parse_preface_sections(preface_text)

    # Parse chapters
    chapters = {}
    for ch_key in ('chapter1', 'chapter2'):
        if ch_key in section_pages:
            ch_num = ch_key[-1]
            ch_text = '\n'.join(
                strip_page_headers_footers(p["text"]) for p in section_pages[ch_key]
            )
            chapters[ch_num] = {
                "title": "Introduction" if ch_num == "1" else "CUI Management",
                "sections": parse_chapter_text(ch_text),
            }

    # Parse appendices
    appendices = {}

    if 'appendix_a' in section_pages:
        a_text = '\n'.join(
            strip_page_headers_footers(p["text"]) for p in section_pages['appendix_a']
        )
        appendices["A"] = {
            "title": "Definitions",
            "entries": parse_definitions(a_text),
        }

    if 'appendix_b' in section_pages:
        b_text = '\n'.join(
            strip_page_headers_footers(p["text"]) for p in section_pages['appendix_b']
        )
        appendices["B"] = {
            "title": "Acronyms",
            "entries": parse_acronyms(b_text),
        }

    if 'appendix_c' in section_pages:
        appendices["C"] = {
            "title": "Requirements Matrices",
            "matrices": parse_requirements_matrices_from_pages(section_pages['appendix_c']),
        }

    if 'appendix_d' in section_pages:
        d_text = '\n'.join(
            strip_page_headers_footers(p["text"]) for p in section_pages['appendix_d']
        )
        appendices["D"] = {
            "title": "Web Resources",
            "entries": parse_web_resources(d_text),
        }

    # Assemble final document
    document = {
        "document_info": doc_info,
        "change_history": change_history,
        "preface": preface,
        "chapters": chapters,
        "appendices": appendices,
    }

    return document


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured JSON from NASA procedural requirement PDFs."
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("output", nargs="?", help="Output JSON file path (default: stdout)")
    parser.add_argument("-o", "--output-file", help="Output JSON file path")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent level (default: 2)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output_file or args.output

    print(f"Extracting: {input_path}", file=sys.stderr)
    document = pdf_to_json(str(input_path))

    json_output = json.dumps(document, indent=args.indent, ensure_ascii=False)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        print(f"Written: {output_path}", file=sys.stderr)

        # Print summary
        sections_count = sum(
            len(ch.get("sections", {})) for ch in document.get("chapters", {}).values()
        )
        preface_count = len(document.get("preface", {}))
        definitions_count = len(document.get("appendices", {}).get("A", {}).get("entries", {}))
        acronyms_count = len(document.get("appendices", {}).get("B", {}).get("entries", {}))
        matrices_count = len(document.get("appendices", {}).get("C", {}).get("matrices", {}))
        resources_count = len(document.get("appendices", {}).get("D", {}).get("entries", []))

        print(f"\nSummary:", file=sys.stderr)
        print(f"  Document: {document['document_info'].get('id', 'Unknown')}", file=sys.stderr)
        print(f"  Pages: {document['document_info'].get('pages', 0)}", file=sys.stderr)
        print(f"  Preface sections: {preface_count}", file=sys.stderr)
        print(f"  Chapter sections: {sections_count}", file=sys.stderr)
        print(f"  Definitions: {definitions_count}", file=sys.stderr)
        print(f"  Acronyms: {acronyms_count}", file=sys.stderr)
        print(f"  Requirements matrices: {matrices_count}", file=sys.stderr)
        print(f"  Web resources: {resources_count}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
