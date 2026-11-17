import json
import os
from pathlib import Path
import unittest
from support.export_comparison import compare


class AtlasExportReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("SENSOR_TEST_CSV") or not os.environ.get("SENSOR_TEST_RECORDED"):
            raise unittest.SkipTest("Requires --suite replay --csv PATH --recorded PATH")
        cls.summary = compare(os.environ["SENSOR_TEST_CSV"], os.environ["SENSOR_TEST_RECORDED"])
        (Path(os.environ["SENSOR_TEST_OUTPUT"]) / "export-comparison.json").write_text(json.dumps(cls.summary, indent=2) + "\n")

    def test_01_all_export_rows_match_recorded_timestamps(self):
        self.assertGreater(self.summary["csv_rows"], 0)
        self.assertEqual(self.summary["unmatched_csv_lines"], [])
        self.assertEqual(self.summary["matched_rows"], self.summary["csv_rows"])

    def test_02_navigation_units_and_altitude_export(self):
        errors = self.summary["max_absolute_error"]
        for key, tolerance in {"latitude": 1e-7, "longitude": 1e-7,
                               "sog_kts": 0.0005, "cog": 0.05}.items():
            with self.subTest(field=key): self.assertLessEqual(errors[key], tolerance)
        # Observed export truncates positive altitude to integer metres.
        self.assertEqual(self.summary["altitude_floor_matches"], self.summary["csv_rows"])

    def test_03_quaternion_and_exported_angle_mapping(self):
        errors = self.summary["max_absolute_error"]
        for key in ["q_w", "q_x", "q_y", "q_z"]:
            with self.subTest(field=key): self.assertLessEqual(errors[key], 5.1e-10)
        # Observed rounded export; tolerances include unnormalized float32 q.
        for key in ["heel", "trim", "hdg_true"]:
            with self.subTest(field=key): self.assertLessEqual(errors[key], 0.06)
