# Beamline Display Language

Beamline Display Language (BDL) is a tiny display contract for epistemic lineage graphs.

It is deliberately boring:

- time flows left → right
- every block has a year column when the year is known
- every edge says whether it is `CLOSED`, `DRIFT`, `OPEN`, or `UNKNOWN`
- renderers must be able to show the same graph in a terminal or browser

## Primitives

### Node

A node is a block-like thing placed on the time axis.

```json
{
  "id": "shannon-1948",
  "label": "Shannon 1948",
  "kind": "source",
  "year": 1948,
  "column": 0,
  "status": "DRIFT"
}
```

Kinds:

- `source` — paper/source artifact
- `concept` — extracted concept block or usage concept
- `artifact` — final manuscript/product/artifact
- `tweet`, `blog`, `note`, `receipt` — public/process receipts
- `unknown` — allowed, but suspicious

### Edge

An edge is a directional beamline segment.

```json
{
  "from": "shannon-1948",
  "to": "shape-of-trust:trust-as-prediction-observation-gap",
  "status": "DRIFT",
  "relation": "imports_measurement_primitive",
  "distance": 0.262468,
  "year_delta": 78
}
```

Status semantics:

- `CLOSED`: the concept survives comparison without material drift
- `DRIFT`: the artifact transforms the source concept
- `OPEN`: process/constitutive edge without a closure receipt yet
- `UNKNOWN`: no receipt or status available

DRIFT is not failure. Pretending drift is closure is failure.

## CLI

Convert an existing lineage graph:

```bash
beamline-display convert path/to/lineage-graph.json --out beamline.display.json --title "Shape of Trust"
```

Render terminal view:

```bash
beamline-display terminal beamline.display.json
```

Render self-contained HTML:

```bash
beamline-display html beamline.display.json --out beamline.html
```

The HTML file has no external dependencies. Open it directly in a browser.
