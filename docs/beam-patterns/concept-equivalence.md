# Beam Pattern: Concept Equivalence

Use this beam pattern when the artifact being analyzed is a paper and the task is to test whether a referenced term preserves the concept introduced by another paper.

A citation says Paper B points at Paper A. A concept-equivalence artifact says whether Paper B preserves, narrows, broadens, decorates, drifts, or forks the concept from Paper A.

## Core claim

Concept equivalence is not word similarity.

A term is equivalent only if the usage preserves the same conceptual object across these facets:

1. definition — what the term means;
2. causal role — what the term does in the argument or mechanism;
3. assumptions — what must be true for it to apply;
4. scope — where it applies and where it does not;
5. measurement/use — how the paper operationalizes it;
6. exclusions — what the origin paper explicitly rules out;
7. downstream implications — what follows if the concept is accepted.

## BTA mapping

```text
Origin paper span      -> origin concept block
Referencing paper span -> usage concept block
Facet comparison       -> beamline proof of search
Closure/S3 mapping     -> geometric receipt, not final judge
Equivalence report     -> collapsed artifact
```

## Block roles

- `origin`: the paper/span that introduces or canonically defines the concept.
- `usage`: a later paper/span that uses, cites, extends, or borrows the concept.
- `bridge`: an optional intermediate interpretation, survey, textbook, or derivative artifact.

## Closure-SDK role

Closure-SDK is used as a concept-state mapper:

```text
origin facets -> q_origin
usage facets  -> q_usage
Δ = q_origin^-1 ⊗ q_usage
σ(Δ) = geodesic gap
```

This does not magically read papers. The extraction quality still matters. Closure gives an ordered, provenance-preserving geometry over structured concept blocks. It is useful because the same concept facets can be composed in the same order, producing a repeatable state and a measurable gap.

Paranoid caveat: Closure-SDK `embed(bytes)` is deterministic geometry over bytes, not a peer reviewer. If the block text is sloppy, the quaternion will faithfully preserve the slop. The depression is left-invariant.

## Status classes

- `CLOSED`: same concept, same operating role.
- `NEAR_CLOSED`: same concept family, scoped change acknowledged.
- `COMPATIBLE_EXTENSION`: meaning preserved, new application added.
- `NARROWED`: usage keeps the concept but restricts scope.
- `BROADENED`: usage generalizes beyond origin assumptions.
- `DRIFT`: same word, changed mechanism or assumptions.
- `FORK`: usage should be named as a new concept.
- `DECORATIVE`: citation/term appears without doing semantic work.

## Beamline phases

1. `extract_origin`: quote and facet the origin concept.
2. `extract_usage`: quote and facet the referencing usage.
3. `normalize_facets`: put both blocks into the same facet schema without improving the argument.
4. `map_closure`: compose ordered facet states and measure σ gaps.
5. `adversarial_check`: identify the strongest reason the equivalence claim could be false.
6. `collapse`: emit status, score, mismatches, and required renaming/qualification.

## Collapse rule

Do not collapse to `CLOSED` unless:

- definition gap is low;
- causal role is preserved;
- assumptions are compatible;
- exclusions are not violated;
- the referencing paper uses the term as a working mechanism, not a decorative citation.

A good mismatch report is more valuable than a fake equivalence. Scholarship has enough wallpaper.
