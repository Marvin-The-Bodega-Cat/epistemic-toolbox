# Bridge Probe

Bridge Probe searches the space between two drifting concept blocks.

Given an origin block and a usage block, it generates all 128 facet-hybrid bridge candidates:

```text
7 concept facets → each facet chosen from origin or usage → 2^7 candidates
```

For each candidate it measures:

```text
origin → bridge
bridge → usage
```

Then it ranks candidates by:

1. whether either side closes (`CLOSED` or `NEAR_CLOSED`)
2. whether both hops are lower than the direct drift
3. lowest max-hop distance
4. lowest total two-hop distance
5. balanced left/right distances

The output is not evidence. It is a search target.

A generated bridge says:

> If we can find or write a real block with this facet shape, this is the likely place where the beamline can stop drifting so much.

## Commands

Probe one pair:

```bash
bridge-probe pair origin.concept-block.json usage.concept-block.json --out bridge-probe.json
```

Probe a full lineage index:

```bash
bridge-probe index lineage-block-pairs.index.json --outdir bridge-probe-output
```

Outputs:

- `bridge-probe-summary.json`
- `bridge-probe-report.md`
- `pairs/*.bridge-probe.json`
- `bridge-blocks/*.concept-block.json`

## Interpretation

- `direct_distance`: measured source → usage drift
- `left_distance`: source → synthetic bridge drift
- `right_distance`: synthetic bridge → usage drift
- `max_hop_distance`: worst side after inserting the bridge
- `max_reduction`: `direct_distance - max_hop_distance`

A good candidate lowers `max_hop_distance`.

A truly useful candidate also has real spans. Synthetic spans are only a map of what to search for.
