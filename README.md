# Epistemic Toolbox

Small tools for turning references, claims, and concepts into inspectable epistemic receipts.

This repo was extracted from Mindware so the paper/concept-analysis machinery can evolve independently from the BTA protocol scaffold.

Mindware link:
https://github.com/Marvin-The-Bodega-Cat/mindware

## Tool 1: concept equivalence

A citation says Paper B points at Paper A.
A concept-equivalence artifact asks whether Paper B preserves the same conceptual object from Paper A.

The tool compares an `origin` concept block and a `usage` concept block across these facets:

- definition
- causal role
- assumptions
- scope
- measurement/use
- exclusions
- downstream implications

If `closure_sdk` is installed, it maps ordered facet states onto S3 and reports the geodesic gap. If not, it falls back to deterministic SHA-256 unit-vector receipts with no semantic claim.

The important caveat is deliberately boring: geometry is a receipt over extracted blocks, not an oracle over raw paper meaning. If the extraction is bad, the receipt is precise about the wrong thing. Academia already has enough footnotes doing that job.

## Quick start

```bash
python3 tools/concept_equivalence.py \
  examples/papers/attention-origin.concept-block.json \
  examples/papers/attention-usage-metaphor.concept-block.json \
  --out receipts/concept-equivalence/attention.synthetic.artifact.json \
  --pretty
```

Expected synthetic result:

```text
status: DRIFT
```

Why: the origin block defines attention as a query/key/value weighted vector mechanism; the usage block uses attention as audience focus in a creator market. Same label. Different object.

## Schemas

- `schemas/concept-block.schema.json`
- `schemas/concept-equivalence-artifact.schema.json`

## Beam pattern

- `docs/beam-patterns/concept-equivalence.md`

## Relationship to Mindware

Mindware supplies the larger BTA frame: blocks, minds, beamlines, proof of search, artifacts.

Epistemic Toolbox supplies reusable epistemic instruments that can be plugged into Mindware runs or used directly.

```text
Mindware:          artifact pipeline
Epistemic Toolbox: concept/reference/claim measurement tools
```
