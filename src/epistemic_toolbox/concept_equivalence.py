#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FACETS = [
    "definition",
    "causal_role",
    "assumptions",
    "scope",
    "measurement_or_use",
    "exclusions",
    "downstream_implications",
]
STATUSES = [
    "CLOSED",
    "NEAR_CLOSED",
    "COMPATIBLE_EXTENSION",
    "NARROWED",
    "BROADENED",
    "DRIFT",
    "FORK",
    "DECORATIVE",
]

try:
    import closure_sdk as cs  # type: ignore
except Exception:  # pragma: no cover - exercised only when dependency missing
    cs = None


class ValidationError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise ValidationError(f"cannot parse {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_block(block: dict[str, Any], path: Path) -> None:
    require(block.get("schema_version") == "mindware.concept.block.v1", f"{path}: bad schema_version")
    for key in ["id", "concept_id", "role", "paper", "spans", "quoted_definition", "local_context", "facets", "known_limits"]:
        require(key in block, f"{path}: missing {key}")
    require(block["role"] in ["origin", "usage", "bridge"], f"{path}: invalid role")
    spans = block.get("spans")
    require(isinstance(spans, list) and len(spans) > 0, f"{path}: spans must be non-empty")
    spans_list = spans if isinstance(spans, list) else []
    for span in spans_list:
        require(isinstance(span, dict), f"{path}: each span must be an object")
        require("locator" in span and "quote" in span, f"{path}: each span needs locator and quote")
    facets = block.get("facets")
    require(isinstance(facets, dict), f"{path}: facets must be object")
    facet_map = facets if isinstance(facets, dict) else {}
    for facet in FACETS:
        require(facet in facet_map, f"{path}: missing facet {facet}")
        require(isinstance(facet_map[facet], list), f"{path}: facet {facet} must be list")
    paper = block.get("paper")
    require(isinstance(paper, dict), f"{path}: paper must be object")
    paper_map = paper if isinstance(paper, dict) else {}
    for key in ["title", "authors", "year", "uri"]:
        require(key in paper_map, f"{path}: paper missing {key}")


def facet_text(block: dict[str, Any], facet: str) -> str:
    values = block["facets"].get(facet, [])
    return "\n".join(str(v).strip() for v in values if str(v).strip())


def block_payload(block: dict[str, Any], facets: list[str]) -> str:
    lines = [
        f"concept_id: {block['concept_id']}",
        f"role: {block['role']}",
        f"quoted_definition: {block['quoted_definition']}",
        f"local_context: {block['local_context']}",
    ]
    for facet in facets:
        lines.append(f"facet:{facet}: {facet_text(block, facet)}")
    return "\n".join(lines)


def fallback_embed(payload: str) -> list[float]:
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    vals = []
    for idx in range(4):
        chunk = digest[idx * 8 : (idx + 1) * 8]
        raw = int.from_bytes(chunk, "big", signed=False)
        vals.append((raw / ((1 << 64) - 1)) * 2.0 - 1.0)
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def fallback_sigma(a: list[float], b: list[float]) -> float:
    dot = abs(sum(x * y for x, y in zip(a, b)))
    dot = max(-1.0, min(1.0, dot))
    return math.acos(dot)


def ordered_closure_state(block: dict[str, Any], facets: list[str]) -> Any:
    if cs is None:
        return fallback_embed(block_payload(block, facets))
    state = cs.embed(f"concept:{block['concept_id']}".encode())
    for facet in facets:
        payload = f"{facet}\n{facet_text(block, facet)}".encode()
        state = cs.compose(state, cs.embed(payload))
    return state


def sigma_between(a: Any, b: Any) -> float:
    if cs is None:
        return fallback_sigma(a, b)
    return float(cs.sigma(cs.compose(cs.invert(a), b)))


def tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9_]+", text.lower()) if len(tok) > 2}


def lexical_overlap(a: str, b: str) -> float:
    aa = tokenize(a)
    bb = tokenize(b)
    if not aa and not bb:
        return 1.0
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def facet_verdict(normalized_distance: float, overlap: float) -> str:
    if normalized_distance <= 0.15 and overlap >= 0.35:
        return "preserved"
    if normalized_distance <= 0.35 or overlap >= 0.25:
        return "compatible_or_needs_review"
    if normalized_distance <= 0.70:
        return "drift_risk"
    return "mismatch"


def collapse_status(overall: float, facet_results: list[dict[str, Any]], origin: dict[str, Any], usage: dict[str, Any]) -> tuple[str, list[str]]:
    mismatches: list[str] = []
    by_facet = {r["facet"]: r for r in facet_results}
    for facet in ["definition", "causal_role", "assumptions", "exclusions"]:
        result = by_facet[facet]
        if result["verdict"] in ["drift_risk", "mismatch"]:
            mismatches.append(f"{facet}: {result['verdict']} (normalized_distance={result['normalized_distance']:.3f}, lexical_overlap={result['lexical_overlap']:.3f})")

    usage_payload = block_payload(usage, FACETS).lower()
    decorative = all(word not in usage_payload for word in ["mechanism", "operational", "measure", "score", "model", "use", "causal", "feedback"])
    if decorative:
        return "DECORATIVE", mismatches + ["usage block lacks operational language"]

    if by_facet["definition"]["verdict"] == "mismatch" or by_facet["causal_role"]["verdict"] == "mismatch":
        return "FORK", mismatches
    if mismatches or overall > 0.35:
        return "DRIFT", mismatches
    if overall <= 0.15 and all(r["verdict"] == "preserved" for r in facet_results):
        return "CLOSED", mismatches
    if overall <= 0.25:
        return "NEAR_CLOSED", mismatches
    return "COMPATIBLE_EXTENSION", mismatches


def compare(origin: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    require(origin["concept_id"] == usage["concept_id"], "concept_id mismatch")
    origin_state = ordered_closure_state(origin, FACETS)
    usage_state = ordered_closure_state(usage, FACETS)
    sigma = sigma_between(origin_state, usage_state)
    normalized = sigma / math.pi

    facet_results = []
    for facet in FACETS:
        o_text = facet_text(origin, facet)
        u_text = facet_text(usage, facet)
        f_sigma = sigma_between(ordered_closure_state({**origin, "facets": {facet: origin["facets"][facet]}}, [facet]), ordered_closure_state({**usage, "facets": {facet: usage["facets"][facet]}}, [facet]))
        f_norm = f_sigma / math.pi
        overlap = lexical_overlap(o_text, u_text)
        verdict = facet_verdict(f_norm, overlap)
        facet_results.append(
            {
                "facet": facet,
                "sigma": round(f_sigma, 6),
                "normalized_distance": round(f_norm, 6),
                "lexical_overlap": round(overlap, 6),
                "verdict": verdict,
                "note": "Geometric receipt over extracted facet text; human review required for semantic finality.",
            }
        )

    status, mismatches = collapse_status(normalized, facet_results, origin, usage)
    backend = "closure_sdk_1.0.0" if cs is not None else "sha256_s3_fallback"
    warnings = [
        "Closure geometry is a receipt over structured extraction, not an oracle over raw paper meaning.",
        "CLOSED requires reviewer acceptance of the extracted facets, not only a low sigma score.",
    ]
    if backend == "sha256_s3_fallback":
        warnings.append("closure_sdk unavailable; used deterministic S3 fallback with no semantic claim.")

    return {
        "schema_version": "mindware.concept.equivalence.v1",
        "artifact_id": f"artifact-concept-equivalence-{origin['concept_id']}-{origin['id'].replace('concept-block-', '')}-vs-{usage['id'].replace('concept-block-', '')}",
        "concept_id": origin["concept_id"],
        "origin_block": origin["id"],
        "usage_block": usage["id"],
        "method": "BTA concept-equivalence beam pattern: extracted facets, ordered Closure-SDK S3 composition, per-facet mismatch receipts, collapse status.",
        "closure": {
            "backend": backend,
            "ordered_facets": FACETS,
            "sigma": round(sigma, 6),
            "normalized_distance": round(normalized, 6),
        },
        "facet_results": facet_results,
        "status": status,
        "collapse_decision": f"Collapsed as {status}. Treat the citation as concept-preserving only if reviewer accepts the facet extraction and the listed mismatches are resolved.",
        "mismatches": mismatches,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Create a concept-equivalence artifact from origin and usage concept blocks.")
    parser.add_argument("origin", help="origin concept block JSON")
    parser.add_argument("usage", help="usage concept block JSON")
    parser.add_argument("--out", help="write artifact JSON to this path")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args(argv)

    try:
        origin_path = Path(args.origin)
        usage_path = Path(args.usage)
        if not origin_path.is_absolute():
            origin_path = ROOT / origin_path
        if not usage_path.is_absolute():
            usage_path = ROOT / usage_path
        origin = load_json(origin_path)
        usage = load_json(usage_path)
        validate_block(origin, origin_path)
        validate_block(usage, usage_path)
        require(origin["role"] == "origin", "first block must have role=origin")
        require(usage["role"] in ["usage", "bridge"], "second block must have role=usage or bridge")
        artifact = compare(origin, usage)
    except ValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        print(f"wrote: {out_path}")
        print(f"status: {artifact['status']}")
        print(f"normalized_distance: {artifact['closure']['normalized_distance']}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
