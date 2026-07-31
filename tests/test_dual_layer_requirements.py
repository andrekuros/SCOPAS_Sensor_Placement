"""Tests for dual-layer requirement checking."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from scopas_metrics import check_dual_layer_requirements


class DualLayerRequirementsTests(unittest.TestCase):
    def test_meets_both_targets(self):
        status = check_dual_layer_requirements(
            {"M_wp_coop": 0.92, "M_wp_noncoop": 0.55},
            min_M_wp_coop=0.90,
            min_M_wp_noncoop=0.50,
        )
        self.assertTrue(status["meets_all"])
        self.assertEqual(status["status"], "green")

    def test_fails_noncoop_only(self):
        status = check_dual_layer_requirements(
            {"M_wp_coop": 0.95, "M_wp_noncoop": 0.40},
            min_M_wp_coop=0.90,
            min_M_wp_noncoop=0.50,
        )
        self.assertFalse(status["meets_all"])
        self.assertTrue(status["meets_M_wp_coop"])
        self.assertFalse(status["meets_M_wp_noncoop"])
        self.assertEqual(status["status"], "yellow")

    def test_fails_both(self):
        status = check_dual_layer_requirements(
            {"M_wp_coop": 0.80, "M_wp_noncoop": 0.30},
            min_M_wp_coop=0.90,
            min_M_wp_noncoop=0.50,
        )
        self.assertFalse(status["meets_all"])
        self.assertEqual(status["status"], "red")

    def test_empty_metrics_fail(self):
        status = check_dual_layer_requirements({}, min_M_wp_coop=0.90, min_M_wp_noncoop=0.50)
        self.assertFalse(status["meets_all"])
        self.assertEqual(status["M_wp_coop"], 0.0)
        self.assertEqual(status["M_wp_noncoop"], 0.0)


if __name__ == "__main__":
    unittest.main()
