from __future__ import annotations

import argparse
import html
import json
import math
import re
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

STATUS_ORDER = {"CLOSED": 0, "DRIFT": 1, "OPEN": 2, "UNKNOWN": 3}
STATUS_GLYPH = {"CLOSED": "●", "DRIFT": "◇", "OPEN": "○", "UNKNOWN": "?"}
STATUS_COLOR = {"CLOSED": "#32d583", "DRIFT": "#fdb022", "OPEN": "#94a3b8", "UNKNOWN": "#64748b"}
KIND_COLOR = {
    "source": "#1d4ed8",
    "concept": "#7c3aed",
    "artifact": "#be123c",
    "tweet": "#0891b2",
    "blog": "#0f766e",
    "note": "#475569",
    "receipt": "#b45309",
    "unknown": "#334155",
}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def write_json(path: str | Path, data: Any, pretty: bool = True) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False) + "\n")


def slug_label(node_id: str) -> str:
    label = node_id.split(":", 1)[-1]
    label = re.sub(r"^(shape-of-trust[-:]?)", "", label)
    label = label.replace("-", " ").replace("_", " ")
    return " ".join(w.capitalize() if w not in {"of", "and", "to", "as", "s3"} else w.upper() if w == "s3" else w for w in label.split())


def infer_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and 1000 <= value <= 3000:
        return value
    if isinstance(value, str):
        m = re.search(r"(18|19|20)\d{2}", value)
        if m:
            return int(m.group(0))
    return None


def infer_kind(raw: dict[str, Any]) -> str:
    t = raw.get("type", "")
    node_id = raw.get("id", "")
    if t == "source_artifact":
        return "source"
    if t == "shape_of_trust_usage_concept" or ":" in node_id and "shape-of-trust:" in node_id:
        return "concept"
    if t == "paper_artifact" or node_id.endswith(":artifact"):
        return "artifact"
    if t == "public_tweet" or node_id.startswith("tweet:"):
        return "tweet"
    if "blog" in t:
        return "blog"
    if "note" in t:
        return "note"
    return "unknown"


def edge_status(edge: dict[str, Any]) -> str:
    status = str(edge.get("equivalence_status") or edge.get("status") or "").upper()
    if status in {"CLOSED", "DRIFT", "OPEN", "UNKNOWN"}:
        return status
    if "normalized_distance" in edge or "distance" in edge:
        return "DRIFT"
    if edge.get("relation") in {"constitutes_artifact_shape", "public_release_or_process_receipt"}:
        return "OPEN"
    return "UNKNOWN"


def node_status(node_id: str, incoming: list[dict[str, Any]], outgoing: list[dict[str, Any]]) -> str:
    statuses = [edge_status(e) for e in incoming + outgoing]
    if not statuses:
        return "UNKNOWN"
    if any(s == "DRIFT" for s in statuses):
        return "DRIFT"
    if any(s == "OPEN" for s in statuses):
        return "OPEN"
    if all(s == "CLOSED" for s in statuses):
        return "CLOSED"
    return "UNKNOWN"


def enrich_year_from_edge_blocks(edge: dict[str, Any]) -> int | None:
    for key in ("origin_block", "usage_block"):
        p = edge.get(key)
        if not p:
            continue
        path = Path(p)
        if path.exists():
            try:
                block = load_json(path)
                y = infer_year(block.get("paper", {}).get("year"))
                if y:
                    return y
            except Exception:
                pass
    return None


def convert_lineage_graph(graph: dict[str, Any], title: str | None = None) -> dict[str, Any]:
    raw_nodes = {n["id"]: n for n in graph.get("nodes", [])}
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in graph.get("edges", []):
        outgoing[e.get("from", "")].append(e)
        incoming[e.get("to", "")].append(e)

    node_years: dict[str, int | None] = {}
    for node_id, raw in raw_nodes.items():
        year = infer_year(raw.get("year")) or infer_year(raw.get("created_at")) or infer_year(raw.get("id")) or infer_year(raw.get("path")) or infer_year(raw.get("url"))
        node_years[node_id] = year
    for e in graph.get("edges", []):
        src, dst = e.get("from"), e.get("to")
        if src and node_years.get(src) is None:
            node_years[src] = enrich_year_from_edge_blocks(e) or node_years.get(src)
        if dst and node_years.get(dst) is None:
            # Usage blocks are usually the artifact year; fall back to predecessor year below.
            y = None
            usage = e.get("usage_block")
            if usage and Path(usage).exists():
                try:
                    y = infer_year(load_json(usage).get("paper", {}).get("year"))
                except Exception:
                    y = None
            node_years[dst] = y or node_years.get(dst)

    # If an artifact/process node has no explicit year, place it at the latest
    # known predecessor year. Otherwise final artifacts fall into "unknown" even
    # when all constitutive concepts are dated, which makes the time graph lie by
    # omission. Boring bug, expensive interpretation.
    changed = True
    while changed:
        changed = False
        for e in graph.get("edges", []):
            src, dst = e.get("from"), e.get("to")
            if dst and node_years.get(dst) is None:
                sy = node_years.get(src)
                if isinstance(sy, int):
                    node_years[dst] = sy
                    changed = True

    known_years = sorted({y for y in node_years.values() if isinstance(y, int)})
    year_to_col = {y: i for i, y in enumerate(known_years)}
    min_year = min(known_years) if known_years else None
    max_year = max(known_years) if known_years else None

    nodes = []
    for node_id, raw in raw_nodes.items():
        year = node_years.get(node_id)
        kind = infer_kind(raw)
        nodes.append({
            "id": node_id,
            "label": raw.get("label") or slug_label(node_id),
            "kind": kind,
            "year": year,
            "column": year_to_col.get(year),
            "status": node_status(node_id, incoming[node_id], outgoing[node_id]),
            "subtitle": raw.get("type") or kind,
            "url": raw.get("url", ""),
            "source_ref": raw.get("path", ""),
            "metadata": {k: v for k, v in raw.items() if k not in {"id", "label", "type", "url", "path"}},
        })
    nodes.sort(key=lambda n: (9999 if n["year"] is None else n["year"], n["kind"], n["label"]))

    edges = []
    for i, e in enumerate(graph.get("edges", []), 1):
        src, dst = e.get("from"), e.get("to")
        sy, dy = node_years.get(src), node_years.get(dst)
        delta = dy - sy if isinstance(sy, int) and isinstance(dy, int) else None
        distance = e.get("normalized_distance", e.get("distance"))
        status = edge_status(e)
        label_bits = [e.get("relation", "")]
        if delta is not None:
            label_bits.append(f"Δ{delta}y")
        if distance is not None:
            label_bits.append(f"d={distance}")
        edges.append({
            "id": e.get("id") or f"edge-{i:03d}",
            "from": src,
            "to": dst,
            "status": status,
            "relation": e.get("relation", ""),
            "distance": distance,
            "year_delta": delta,
            "label": " | ".join(b for b in label_bits if b),
            "receipt_ref": e.get("artifact", ""),
            "metadata": {k: v for k, v in e.items() if k not in {"id", "from", "to", "status", "relation", "distance", "normalized_distance", "artifact"}},
        })

    return {
        "schema_version": "epistemic.beamline.display.v1",
        "id": graph.get("artifact_id", "beamline-display"),
        "title": title or graph.get("artifact_id", "Beamline Display"),
        "description": graph.get("warning", ""),
        "time_axis": {"direction": "left-to-right", "unit": "year", "min_year": min_year, "max_year": max_year},
        "legend": {
            "CLOSED": "Concept preserved / closed by receipt",
            "DRIFT": "Concept transformed / semantic drift detected",
            "OPEN": "Process or constitutive edge without closure test",
            "UNKNOWN": "No closure receipt available",
        },
        "nodes": nodes,
        "edges": edges,
    }


def render_terminal(display: dict[str, Any], width: int = 120) -> str:
    nodes_by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in display["nodes"]:
        key = str(n["year"]) if n["year"] is not None else "unknown"
        nodes_by_year[key].append(n)
    year_keys = sorted(nodes_by_year, key=lambda y: 9999 if y == "unknown" else int(y))
    lines = [display["title"], "=" * min(len(display["title"]), width), ""]
    desc = display.get("description") or ""
    if desc:
        lines.extend(textwrap.wrap(desc, width=width))
        lines.append("")
    lines.append("Legend: ● CLOSED   ◇ DRIFT   ○ OPEN   ? UNKNOWN")
    lines.append("Time: left → right by year")
    lines.append("")
    for y in year_keys:
        lines.append(f"[{y}]")
        for n in sorted(nodes_by_year[y], key=lambda x: (STATUS_ORDER.get(x["status"], 9), x["kind"], x["label"])):
            glyph = STATUS_GLYPH.get(n["status"], "?")
            label = n["label"][:54]
            lines.append(f"  {glyph} {label:<54} ({n['kind']}) {n['id']}")
        lines.append("")
    lines.append("Edges")
    lines.append("-----")
    for e in sorted(display["edges"], key=lambda x: (display_node_year(display, x["from"]), display_node_year(display, x["to"]), x["from"], x["to"])):
        glyph = STATUS_GLYPH.get(e["status"], "?")
        delta = "?y" if e["year_delta"] is None else f"{e['year_delta']}y"
        distance = "" if e["distance"] is None else f" d={e['distance']}"
        lines.append(f"{glyph} {e['from']} ──[{e['relation']} Δ{delta}{distance}]──> {e['to']}")
    return "\n".join(lines) + "\n"


def display_node_year(display: dict[str, Any], node_id: str) -> int:
    for n in display["nodes"]:
        if n["id"] == node_id:
            return 9999 if n["year"] is None else int(n["year"])
    return 9999


def render_html(display: dict[str, Any]) -> str:
    years = sorted({n["year"] for n in display["nodes"] if n["year"] is not None})
    if not years:
        years = [0]
    year_to_x = {y: 120 + i * 260 for i, y in enumerate(years)}
    lanes: dict[int | None, int] = defaultdict(int)
    positions: dict[str, tuple[int, int]] = {}
    ordered = sorted(display["nodes"], key=lambda n: (9999 if n["year"] is None else n["year"], n["kind"], n["label"]))
    for n in ordered:
        y = n["year"] if n["year"] is not None else years[-1] + 1
        x = year_to_x.get(y, year_to_x[years[-1]] + 260)
        lane = lanes[y]
        lanes[y] += 1
        positions[n["id"]] = (x, 110 + lane * 92)
    width = max(x for x, _ in positions.values()) + 180 if positions else 800
    height = max(y for _, y in positions.values()) + 140 if positions else 600
    edge_svg = []
    for e in display["edges"]:
        if e["from"] not in positions or e["to"] not in positions:
            continue
        x1, y1 = positions[e["from"]]
        x2, y2 = positions[e["to"]]
        color = STATUS_COLOR.get(e["status"], "#64748b")
        dash = "6 5" if e["status"] == "DRIFT" else "" if e["status"] == "CLOSED" else "2 5"
        midx, midy = (x1 + x2) / 2, (y1 + y2) / 2 - 8
        path = f"M {x1+80} {y1} C {x1+150} {y1}, {x2-150} {y2}, {x2-80} {y2}"
        edge_svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}" marker-end="url(#arrow-{e["status"]})"><title>{html.escape(e["label"])}</title></path>')
        edge_svg.append(f'<text x="{midx}" y="{midy}" text-anchor="middle" class="edge-label">{html.escape(short_edge_label(e))}</text>')
    year_svg = []
    for y, x in year_to_x.items():
        year_svg.append(f'<line x1="{x}" y1="58" x2="{x}" y2="{height-40}" class="year-line"/>')
        year_svg.append(f'<text x="{x}" y="40" text-anchor="middle" class="year-label">{y}</text>')
    node_svg = []
    for n in ordered:
        x, y = positions[n["id"]]
        color = STATUS_COLOR.get(n["status"], "#64748b")
        fill = KIND_COLOR.get(n["kind"], "#334155")
        label = html.escape(n["label"][:28] + ("…" if len(n["label"]) > 28 else ""))
        subtitle = html.escape(f"{n['kind']} · {n['status']}")
        node_svg.append(f'<g class="node" transform="translate({x-78},{y-30})"><rect width="156" height="60" rx="12" fill="{fill}" stroke="{color}" stroke-width="3"><title>{html.escape(n["id"])}</title></rect><text x="78" y="24" text-anchor="middle" class="node-label">{label}</text><text x="78" y="44" text-anchor="middle" class="node-subtitle">{subtitle}</text></g>')
    legend = " ".join(f'<span><b style="color:{STATUS_COLOR[k]}">{STATUS_GLYPH[k]}</b> {k}</span>' for k in ["CLOSED", "DRIFT", "OPEN", "UNKNOWN"])
    data_script = html.escape(json.dumps(display, ensure_ascii=False))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(display['title'])}</title>
<style>
body {{ margin:0; background:#020617; color:#e5e7eb; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
header {{ padding:20px 24px 8px; border-bottom:1px solid #1e293b; position:sticky; top:0; background:rgba(2,6,23,.94); z-index:2; }}
h1 {{ margin:0 0 8px; font-size:22px; }} .desc {{ color:#94a3b8; max-width:1100px; line-height:1.4; }}
.legend {{ display:flex; gap:18px; margin-top:12px; color:#cbd5e1; font-size:13px; }}
.wrap {{ overflow:auto; height:calc(100vh - 120px); }} svg {{ min-width:{width}px; min-height:{height}px; }}
.year-line {{ stroke:#1e293b; stroke-width:1; }} .year-label {{ fill:#f8fafc; font-size:16px; font-weight:700; }}
.node-label {{ fill:#fff; font-size:11px; font-weight:700; pointer-events:none; }} .node-subtitle {{ fill:#cbd5e1; font-size:10px; pointer-events:none; }}
.edge-label {{ fill:#cbd5e1; font-size:10px; paint-order:stroke; stroke:#020617; stroke-width:4px; stroke-linejoin:round; }}
</style></head><body>
<header><h1>{html.escape(display['title'])}</h1><div class="desc">{html.escape(display.get('description',''))}</div><div class="legend">{legend}<span>time flows left → right</span></div></header>
<div class="wrap"><svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>{''.join(arrow_marker(k, v) for k, v in STATUS_COLOR.items())}</defs>
{''.join(year_svg)}
{''.join(edge_svg)}
{''.join(node_svg)}
</svg></div>
<script type="application/json" id="beamline-data">{data_script}</script>
</body></html>"""


def short_edge_label(e: dict[str, Any]) -> str:
    bits = []
    if e.get("year_delta") is not None:
        bits.append(f"Δ{e['year_delta']}y")
    bits.append(e.get("status", ""))
    if e.get("distance") is not None:
        bits.append(f"d={e['distance']}")
    return " ".join(bits)


def arrow_marker(status: str, color: str) -> str:
    return f'<marker id="arrow-{status}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L7,3 z" fill="{color}" /></marker>'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render epistemic beamlines as display-language JSON, terminal text, or static HTML.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="Convert a lineage graph into Beamline Display Language JSON")
    c.add_argument("input")
    c.add_argument("--out", required=True)
    c.add_argument("--title", default=None)
    t = sub.add_parser("terminal", help="Render Beamline Display Language JSON to terminal text")
    t.add_argument("input")
    t.add_argument("--out")
    t.add_argument("--width", type=int, default=120)
    w = sub.add_parser("html", help="Render Beamline Display Language JSON to static HTML")
    w.add_argument("input")
    w.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "convert":
        display = convert_lineage_graph(load_json(args.input), title=args.title)
        write_json(args.out, display)
        print(args.out)
        return 0
    if args.cmd == "terminal":
        text = render_terminal(load_json(args.input), width=args.width)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(args.out)
        else:
            print(text, end="")
        return 0
    if args.cmd == "html":
        html_text = render_html(load_json(args.input))
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(html_text)
        print(args.out)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
