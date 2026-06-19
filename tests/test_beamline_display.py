import json
import tempfile
import unittest
from pathlib import Path

from epistemic_toolbox.beamline_display import convert_lineage_graph, render_html, render_terminal


class BeamlineDisplayTests(unittest.TestCase):
    def test_convert_left_to_right_years_and_statuses(self):
        graph = json.loads(Path("examples/beamlines/synthetic-lineage-graph.json").read_text())
        display = convert_lineage_graph(graph, title="Synthetic")
        self.assertEqual(display["schema_version"], "epistemic.beamline.display.v1")
        self.assertEqual(display["time_axis"]["direction"], "left-to-right")
        self.assertEqual(display["time_axis"]["min_year"], 1948)
        self.assertEqual(display["time_axis"]["max_year"], 2026)
        edges = {e["relation"]: e for e in display["edges"]}
        self.assertEqual(edges["imports_measurement_primitive"]["year_delta"], 78)
        self.assertEqual(edges["extends_beyond_source"]["status"], "DRIFT")
        self.assertEqual(edges["constitutes_artifact_shape"]["status"], "OPEN")

    def test_renderers_include_status_and_year_labels(self):
        graph = json.loads(Path("examples/beamlines/synthetic-lineage-graph.json").read_text())
        display = convert_lineage_graph(graph, title="Synthetic")
        terminal = render_terminal(display)
        html = render_html(display)
        self.assertIn("[1948]", terminal)
        self.assertIn("◇", terminal)
        self.assertIn("DRIFT", html)
        self.assertIn("2026", html)
        self.assertIn("left → right", html)


if __name__ == "__main__":
    unittest.main()
