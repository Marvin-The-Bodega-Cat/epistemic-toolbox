import json
import tempfile
import unittest
from pathlib import Path

from epistemic_toolbox.bridge_probe import probe_pair, synthesize_bridge_block
from epistemic_toolbox.concept_equivalence import FACETS, load_json, validate_block


class BridgeProbeTests(unittest.TestCase):
    def test_synthesized_bridge_is_valid_and_records_facet_sources(self):
        origin = load_json(Path("examples/papers/attention-origin.concept-block.json"))
        usage = load_json(Path("examples/papers/attention-usage-metaphor.concept-block.json"))
        block = synthesize_bridge_block(origin, usage, mask=1)
        validate_block(block, Path("synthetic"))
        self.assertEqual(block["role"], "bridge")
        self.assertEqual(block["bridge_probe"]["facet_sources"]["definition"], "usage")
        self.assertEqual(block["bridge_probe"]["facet_sources"][FACETS[1]], "origin")

    def test_probe_pair_searches_all_facet_hybrids(self):
        result = probe_pair(
            "examples/papers/attention-origin.concept-block.json",
            "examples/papers/attention-usage-metaphor.concept-block.json",
            top=5,
        )
        self.assertEqual(result["searched_candidates"], 128)
        self.assertEqual(len(result["top_candidates"]), 5)
        self.assertIn("max_hop_distance", result["best"])
        self.assertIn("facet_sources", result["best"])
        self.assertLessEqual(result["best"]["max_hop_distance"], 1.0)


if __name__ == "__main__":
    unittest.main()
