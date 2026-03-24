"""
SCOPAS tests — config, environment, evaluation, and CLI.

Run from repo root:
  python -m unittest tests.test_scopas -v

Fast tests only (omit TestNSGA2Smoke), a few seconds — run TestConfig, TestEnvironment,
TestEvaluation, TestCLI, and TestOutputHelpers (see README / DOCUMENTATION.md).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Repo root and src on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scopas_core import (
    load_config,
    load_environment_from_config,
    evaluate_solution,
    run_evaluation,
    get_results_dir,
    make_run_id,
    save_run_results,
)


class TestConfig(unittest.TestCase):
    def test_load_config_valid(self):
        config = load_config(ROOT / "configs" / "quick_test.json")
        self.assertIn("experiment_name", config)
        self.assertIn("environment", config)
        self.assertIn("sensors", config)
        self.assertEqual(config["experiment_name"], "quick_test")

    def test_load_config_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_config(ROOT / "configs" / "nonexistent.json")


class TestEnvironment(unittest.TestCase):
    def test_load_environment_from_config(self):
        config = load_config(ROOT / "configs" / "quick_test.json")
        env = load_environment_from_config(config, base_dir=ROOT)
        self.assertIsNotNone(env)
        locs = env.get_sensor_locations()
        self.assertIsInstance(locs, list)
        self.assertGreater(len(locs), 0)


class TestEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "configs" / "quick_test.json")
        cls.env = load_environment_from_config(cls.config, base_dir=ROOT)
        cls.sensor_types = cls.config.get("sensors", {}).get("types", {})

    def test_evaluate_solution_empty_returns_zeros(self):
        res = evaluate_solution(self.env, [], self.sensor_types)
        self.assertEqual(res["coverage"], 0.0)
        self.assertEqual(res["redundancy"], 0.0)
        self.assertEqual(res["cost"], 0.0)
        self.assertEqual(res["num_sensors"], 0)

    def test_evaluate_solution_single_sensor(self):
        # One sensor at a valid location (use first candidate from env)
        locs = self.env.get_sensor_locations()
        self.assertGreater(len(locs), 0)
        x, y, z = locs[0][:3] if len(locs[0]) >= 3 else (locs[0][0], locs[0][1], 10.0)
        sol = [{"type": "Radar", "x": x, "y": y, "z": z}]
        res = evaluate_solution(self.env, sol, self.sensor_types)
        self.assertIn("coverage", res)
        self.assertIn("redundancy", res)
        self.assertIn("cost", res)
        self.assertEqual(res["num_sensors"], 1)
        self.assertGreaterEqual(res["coverage"], 0.0)
        self.assertLessEqual(res["coverage"], 1.0)
        self.assertGreater(res["cost"], 0)

    def test_run_evaluation_multiple_solutions(self):
        locs = self.env.get_sensor_locations()[:3]
        solutions = []
        for i, loc in enumerate(locs):
            x, y = loc[0], loc[1]
            z = loc[2] if len(loc) > 2 else 10.0
            solutions.append([{"type": "Radar", "x": x, "y": y, "z": z}])
        results = run_evaluation(
            str(ROOT / "configs" / "quick_test.json"),
            solutions,
            base_dir=ROOT,
        )
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("coverage", r)
            self.assertIn("num_sensors", r)
            self.assertEqual(r["num_sensors"], 1)


class TestOutputHelpers(unittest.TestCase):
    def test_make_run_id(self):
        config = {"experiment_name": "test_exp", "output": {}}
        run_id = make_run_id("test_exp", config)
        self.assertTrue(run_id.startswith("test_exp_"))
        self.assertIn("_", run_id)

    def test_get_results_dir_creates_dir(self):
        config = load_config(ROOT / "configs" / "quick_test.json")
        out = get_results_dir(config, run_id="test_run_123")
        self.assertTrue(out.is_dir())
        self.assertIn("quick_test", str(out))
        self.assertIn("test_run_123", str(out))

    def test_save_run_results(self):
        config = load_config(ROOT / "configs" / "quick_test.json")
        population = [[{"type": "Radar", "x": 100, "y": 100, "z": 15}]]
        results = [{"coverage": 0.5, "redundancy": 0.2, "cost": 50000.0, "num_sensors": 1}]
        with tempfile.TemporaryDirectory(prefix="scopas_test_") as tmp:
            config["output"] = {"results_dir": tmp}
            out_dir = save_run_results(config, population, results, run_id="save_test", save_pareto=True)
            self.assertTrue((out_dir / "config.json").exists())
            self.assertTrue((out_dir / "evaluation_results.json").exists())
            self.assertTrue((out_dir / "pareto_front.json").exists())
            with open(out_dir / "evaluation_results.json") as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["coverage"], 0.5)


class TestCLI(unittest.TestCase):
    def test_evaluate_mode(self):
        """Run framework in evaluate mode with a tiny solutions file (subprocess)."""
        import subprocess
        solutions = [
            [{"type": "Radar", "x": 200, "y": 200, "z": 20}],
            [{"type": "EO", "x": 300, "y": 300, "z": 15}],
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(solutions, f)
            sol_path = f.name
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_framework.py"),
                    "--config", str(ROOT / "configs" / "quick_test.json"),
                    "--mode", "evaluate",
                    "--solutions-file", sol_path,
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertIn("Evaluation results", proc.stdout)
            self.assertIn("coverage", proc.stdout)
        finally:
            Path(sol_path).unlink(missing_ok=True)


class TestNSGA2Smoke(unittest.TestCase):
    """Quick NSGA-II run to ensure full pipeline (skip if too slow in CI)."""

    def test_nsga2_quick_run(self):
        config = load_config(ROOT / "configs" / "quick_test.json")
        # Already minimal: 8 samples, 3 generations
        from solutions.nsga2 import run as nsga2_run
        population, results, _logbook = nsga2_run(
            config, config_path=str(ROOT / "configs" / "quick_test.json"), base_dir=ROOT
        )
        self.assertIsInstance(population, list)
        self.assertIsInstance(results, list)
        self.assertEqual(len(population), len(results))
        if population:
            self.assertIn("coverage", results[0])
            self.assertIn("cost", results[0])
            self.assertGreaterEqual(len(population[0]), config.get("pareto_search", {}).get("min_sensors", 1))


if __name__ == "__main__":
    unittest.main()
