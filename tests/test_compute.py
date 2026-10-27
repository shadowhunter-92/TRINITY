import math
import unittest

from trinitylab.compute.core import (BatchedEngine, NumpyEngine, ReferenceEngine,
                                     benchmark, compare_outputs, make_inputs, make_model)


class ComputeTests(unittest.TestCase):
    def setUp(self):
        self.model = make_model(6, 5, 3, seed=22)
        self.batch = make_inputs(4, 6, seed=23)

    def test_seed_reproducibility(self):
        self.assertEqual(make_model(6, 5, 3, 22), self.model)
        self.assertEqual(make_inputs(4, 6, 23), self.batch)

    def test_python_paths_agree(self):
        a = ReferenceEngine(self.model).infer(self.batch)
        b = BatchedEngine(self.model).infer(self.batch)
        self.assertTrue(compare_outputs(a, b)["passed"])

    def test_numpy_path_agrees_when_installed(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("NumPy is an optional dependency")
        a = ReferenceEngine(self.model).infer(self.batch)
        b = NumpyEngine(self.model).infer(self.batch)
        self.assertTrue(compare_outputs(a, b)["passed"])

    def test_rejects_bad_shape_and_nonfinite(self):
        e = ReferenceEngine(self.model)
        with self.assertRaises(ValueError):
            e.infer([[1.0, 2.0]])
        with self.assertRaises(ValueError):
            e.infer([[math.nan] * 6])

    def test_rejects_wrong_dimensions(self):
        with self.assertRaises(ValueError):
            make_model(0, 1, 1)
        with self.assertRaises(ValueError):
            make_inputs(0, 3)

    def test_detects_corruption(self):
        r = compare_outputs([[1.0]], [[2.0]])
        self.assertFalse(r["passed"])
        self.assertEqual(r["failed_elements"], 1)
        self.assertFalse(compare_outputs([[1.0]], [[1.0, 2.0]])["passed"])
        self.assertFalse(compare_outputs([[1.0]], [[math.inf]])["passed"])

    def test_benchmark_report(self):
        result = benchmark([ReferenceEngine(self.model), BatchedEngine(self.model)], self.batch, warmup=1, repeats=3)
        self.assertEqual(len(result["engines"]), 2)
        self.assertTrue(all(e["correctness"]["passed"] for e in result["engines"]))
        self.assertGreater(result["engines"][0]["median_ms"], 0)

    def test_wrong_engine_order(self):
        with self.assertRaises(ValueError):
            benchmark([BatchedEngine(self.model)], self.batch)
