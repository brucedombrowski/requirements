#!/usr/bin/env python3
"""
Generate authority graph visualizations from standards metadata.

Reads all standards/*.json files, builds a directed graph from
authority.derives_from (solid edges) and authority.references
(dashed edges), and outputs in selectable formats.

Usage:
    python tools/authority-graph.py                    # Mermaid to stdout
    python tools/authority-graph.py --format dot       # Graphviz DOT
    python tools/authority-graph.py --format tikz      # TikZ for LaTeX
    python tools/authority-graph.py --format all       # All formats to tools/output/
    python tools/authority-graph.py --no-references    # Authority chain only
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STANDARDS_DIR = REPO_ROOT / "standards"
OUTPUT_DIR = REPO_ROOT / "tools" / "output"

TIER_LABELS = {
    0: "Constitution",
    1: "Statute",
    2: "Executive Order",
    3: "OMB Policy",
    4: "Federal Regulation",
    5: "FIPS",
    6: "NIST SP / NARA",
    7: "Agency Policy",
    8: "Agency Procedure",
    9: "Handbook",
}


def load_standards():
    """Load all standard JSON files and return as dict keyed by id."""
    standards = {}
    for path in sorted(STANDARDS_DIR.glob("*.json")):
        if path.name == "README.md":
            continue
        with open(path) as f:
            data = json.load(f)
        standards[data["id"]] = data
    return standards


def build_edges(standards, include_references=True):
    """Extract edges from authority metadata.

    Returns:
        derives_from_edges: list of (source_id, target_id, metadata)
        reference_edges: list of (source_id, target_id, metadata)
    """
    derives_edges = []
    ref_edges = []

    for sid, std in standards.items():
        authority = std.get("authority", {})
        for edge in authority.get("derives_from", []):
            derives_edges.append((sid, edge["id"], edge))
        if include_references:
            for edge in authority.get("references", []):
                ref_edges.append((sid, edge["id"], edge))

    return derives_edges, ref_edges


def mermaid_safe_id(node_id):
    """Convert a standard ID to a Mermaid-safe node identifier."""
    return node_id.replace("-", "_").replace(" ", "_")


def generate_mermaid(standards, derives_edges, ref_edges):
    """Generate Mermaid graph markup.

    Layout is bottom-to-top (graph BT) so the Constitution sits at the
    top while authority arrows flow upward from each standard to its
    parent — i.e. "child --(is mandated by)--> parent" reads naturally.
    """
    lines = ["graph BT"]

    # Group nodes by tier
    tiers = {}
    for sid, std in standards.items():
        tier = std.get("tier")
        if tier is not None:
            tiers.setdefault(tier, []).append(std)

    # Node definitions with short names
    for tier_num in sorted(tiers.keys()):
        tier_label = TIER_LABELS.get(tier_num, f"Tier {tier_num}")
        lines.append(f"    %% Tier {tier_num}: {tier_label}")
        for std in sorted(tiers[tier_num], key=lambda s: s["id"]):
            safe = mermaid_safe_id(std["id"])
            label = std.get("short_name", std["id"])
            lines.append(f'    {safe}["{label}"]')
        lines.append("")

    # Nodes without tier
    no_tier = [s for s in standards.values() if s.get("tier") is None]
    if no_tier:
        lines.append("    %% No tier assigned")
        for std in sorted(no_tier, key=lambda s: s["id"]):
            safe = mermaid_safe_id(std["id"])
            label = std.get("short_name", std["id"])
            lines.append(f'    {safe}["{label}"]')
        lines.append("")

    # Authority edges (solid arrows): child --> parent, labelled with the
    # child-perspective verb (e.g. "mandated by", "implements").
    if derives_edges:
        lines.append("    %% Authority (derives_from)")
        for src, tgt, meta in derives_edges:
            rel = meta.get("relationship", "")
            label = rel.replace("_", " ") if rel else ""
            src_safe = mermaid_safe_id(src)
            tgt_safe = mermaid_safe_id(tgt)
            if label:
                lines.append(f"    {src_safe} -->|{label}| {tgt_safe}")
            else:
                lines.append(f"    {src_safe} --> {tgt_safe}")
        lines.append("")

    # Reference edges (dotted arrows)
    if ref_edges:
        lines.append("    %% References (lateral)")
        for src, tgt, meta in ref_edges:
            src_safe = mermaid_safe_id(src)
            tgt_safe = mermaid_safe_id(tgt)
            lines.append(f"    {src_safe} -.->|refs| {tgt_safe}")
        lines.append("")

    # Styling by tier
    lines.append("    %% Styling")
    tier_colors = {
        0: "#d4edda",  # green - Constitution
        1: "#cce5ff",  # blue - Statutes
        2: "#fff3cd",  # yellow - EO
        3: "#fce4ec",  # pink - OMB
        4: "#e2e3e5",  # gray - Federal Reg
        5: "#d1ecf1",  # cyan - FIPS
        6: "#e8daef",  # purple - NIST/NARA
        7: "#fdebd0",  # orange - Agency Policy
        8: "#fadbd8",  # salmon - Agency Procedure
        9: "#f5f5dc",  # beige - Handbook
    }
    for tier_num, stds in tiers.items():
        color = tier_colors.get(tier_num, "#ffffff")
        ids = ",".join(mermaid_safe_id(s["id"]) for s in stds)
        lines.append(f"    style {ids} fill:{color}")

    return "\n".join(lines)


def generate_dot(standards, derives_edges, ref_edges):
    """Generate Graphviz DOT format."""
    lines = [
        "digraph authority {",
        '    rankdir=BT;',
        '    node [shape=box, style="rounded,filled", fontname="Helvetica"];',
        '    edge [fontname="Helvetica", fontsize=10];',
        "",
    ]

    tier_colors = {
        0: "#d4edda",
        1: "#cce5ff",
        2: "#fff3cd",
        3: "#fce4ec",
        4: "#e2e3e5",
        5: "#d1ecf1",
        6: "#e8daef",
        7: "#fdebd0",
        8: "#fadbd8",
        9: "#f5f5dc",
    }

    # Group by tier using subgraphs for rank
    tiers = {}
    for sid, std in standards.items():
        tier = std.get("tier")
        if tier is not None:
            tiers.setdefault(tier, []).append(std)

    for tier_num in sorted(tiers.keys()):
        tier_label = TIER_LABELS.get(tier_num, f"Tier {tier_num}")
        color = tier_colors.get(tier_num, "#ffffff")
        lines.append(f"    // Tier {tier_num}: {tier_label}")
        lines.append(f"    subgraph cluster_tier{tier_num} {{")
        lines.append(f'        label="{tier_label}";')
        lines.append(f"        rank=same;")
        lines.append(f'        style=invis;')
        for std in sorted(tiers[tier_num], key=lambda s: s["id"]):
            safe = mermaid_safe_id(std["id"])
            label = std.get("short_name", std["id"])
            lines.append(f'        "{safe}" [label="{label}", fillcolor="{color}"];')
        lines.append("    }")
        lines.append("")

    # Authority edges: child -> parent, with the child-perspective verb.
    lines.append("    // Authority edges")
    for src, tgt, meta in derives_edges:
        rel = meta.get("relationship", "")
        src_safe = mermaid_safe_id(src)
        tgt_safe = mermaid_safe_id(tgt)
        label = rel.replace("_", " ") if rel else ""
        if label:
            lines.append(f'    "{src_safe}" -> "{tgt_safe}" [label="{label}"];')
        else:
            lines.append(f'    "{src_safe}" -> "{tgt_safe}";')

    lines.append("")

    # Reference edges
    if ref_edges:
        lines.append("    // Reference edges")
        for src, tgt, meta in ref_edges:
            src_safe = mermaid_safe_id(src)
            tgt_safe = mermaid_safe_id(tgt)
            lines.append(
                f'    "{src_safe}" -> "{tgt_safe}" [style=dashed, color=gray, label="refs"];'
            )

    lines.append("}")
    return "\n".join(lines)


def generate_tikz(standards, derives_edges, ref_edges):
    """Generate TikZ code for LaTeX."""
    lines = [
        "% Authority graph — auto-generated by tools/authority-graph.py",
        "% Requires: \\usepackage{tikz}",
        "% Requires: \\usetikzlibrary{positioning, arrows.meta, calc}",
        "",
        "\\begin{tikzpicture}[",
        "    node distance=1.2cm and 1.5cm,",
        "    every node/.style={",
        "        draw, rounded corners, align=center,",
        "        font=\\small, minimum width=2.5cm, minimum height=0.7cm",
        "    },",
        "    authority/.style={-{Stealth[length=3mm]}, thick},",
        "    reference/.style={-{Stealth[length=2mm]}, dashed, gray},",
        "]",
        "",
    ]

    tier_styles = {
        0: "fill=green!15",
        1: "fill=blue!10",
        2: "fill=yellow!20",
        3: "fill=pink!15",
        4: "fill=gray!15",
        5: "fill=cyan!10",
        6: "fill=violet!10",
        7: "fill=orange!10",
        8: "fill=red!8",
        9: "fill=brown!8",
    }

    # Group by tier
    tiers = {}
    for sid, std in standards.items():
        tier = std.get("tier")
        if tier is not None:
            tiers.setdefault(tier, []).append(std)

    # Place nodes tier by tier
    prev_tier_first = None
    for tier_num in sorted(tiers.keys()):
        stds = sorted(tiers[tier_num], key=lambda s: s["id"])
        style = tier_styles.get(tier_num, "")
        tier_label = TIER_LABELS.get(tier_num, f"Tier {tier_num}")
        lines.append(f"    % Tier {tier_num}: {tier_label}")
        for i, std in enumerate(stds):
            safe = mermaid_safe_id(std["id"]).lower()
            label = std.get("short_name", std["id"]).replace("&", "\\&")
            if i == 0 and prev_tier_first is not None:
                pos = f"below=of {prev_tier_first}"
            elif i > 0:
                prev_safe = mermaid_safe_id(stds[i - 1]["id"]).lower()
                pos = f"right=of {prev_safe}"
            else:
                pos = ""

            pos_str = f"[{style}, {pos}]" if pos else f"[{style}]"
            lines.append(f"    \\node {pos_str} ({safe}) {{{label}}};")

        if stds:
            prev_tier_first = mermaid_safe_id(stds[0]["id"]).lower()
        lines.append("")

    # Authority edges: arrow from child to parent.
    lines.append("    % Authority edges")
    for src, tgt, meta in derives_edges:
        src_safe = mermaid_safe_id(src).lower()
        tgt_safe = mermaid_safe_id(tgt).lower()
        lines.append(f"    \\draw[authority] ({src_safe}) -- ({tgt_safe});")

    lines.append("")

    # Reference edges
    if ref_edges:
        lines.append("    % Reference edges")
        for src, tgt, meta in ref_edges:
            src_safe = mermaid_safe_id(src).lower()
            tgt_safe = mermaid_safe_id(tgt).lower()
            lines.append(f"    \\draw[reference] ({src_safe}) -- ({tgt_safe});")

    lines.append("")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate authority graph visualizations from standards metadata."
    )
    parser.add_argument(
        "--format",
        choices=["mermaid", "dot", "tikz", "all"],
        default="mermaid",
        help="Output format (default: mermaid)",
    )
    parser.add_argument(
        "--no-references",
        action="store_true",
        help="Omit lateral reference edges, show authority chain only",
    )
    args = parser.parse_args()

    standards = load_standards()
    include_refs = not args.no_references
    derives_edges, ref_edges = build_edges(standards, include_references=include_refs)

    node_count = len(standards)
    edge_count = len(derives_edges) + len(ref_edges)

    generators = {
        "mermaid": (generate_mermaid, "authority-graph.mmd"),
        "dot": (generate_dot, "authority-graph.dot"),
        "tikz": (generate_tikz, "authority-graph.tex"),
    }

    if args.format == "all":
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for fmt, (gen_fn, filename) in generators.items():
            output = gen_fn(standards, derives_edges, ref_edges)
            out_path = OUTPUT_DIR / filename
            with open(out_path, "w") as f:
                f.write(output)
                f.write("\n")
            print(f"  {fmt:8s} -> {out_path.relative_to(REPO_ROOT)}")
        print(f"\n{node_count} nodes, {edge_count} edges")
    else:
        gen_fn, filename = generators[args.format]
        output = gen_fn(standards, derives_edges, ref_edges)
        print(output)
        print(f"\n%% {node_count} nodes, {edge_count} edges", file=sys.stderr)


if __name__ == "__main__":
    main()
