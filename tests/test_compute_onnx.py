"""Always-runnable security tests plus optional real ONNX integration tests."""
import math
import unittest
from unittest.mock import patch

from trinitylab.compute.core import (
    ReferenceEngine, benchmark, compare_outputs, make_inputs, make_model
)
from trinitylab.compute.onnx_adapter import (
    MissingONNXDependencies, ONNXRuntimeCPUEngine, _load_dependencies
)


class AdapterAvailabilityTests(unittest.TestCase):
    def test_import_is_safe_without_optional_packages(self):
        self.assertEqual(ONNXRuntimeCPUEngine.name, "onnxruntime_cpu_float32")

    def test_missing_packages_message_contains_install_command(self):
        from trinitylab.compute import onnx_adapter
        with patch.object(onnx_adapter.importlib, "import_module", side_effect=ImportError("not installed")):
            with self.assertRaisesRegex(MissingONNXDependencies, "compute-onnx"):
                _load_dependencies()


class RealONNXRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            _load_dependencies()
        except MissingONNXDependencies:
            raise unittest.SkipTest("Install optional extras: pip install -e '.[compute-onnx]'")
        cls.model = make_model(input_dim=6, hidden_dim=5, output_dim=3, seed=22)
        cls.batch = make_inputs(4, 6, seed=23)

    def test_float32_cpu_parity_against_reference(self):
        a = ReferenceEngine(self.model).infer(self.batch)
        b = ONNXRuntimeCPUEngine(self.model).infer(self.batch)
        self.assertTrue(compare_outputs(a, b, atol=1e-5, rtol=1e-4)["passed"])

    def test_local_model_and_runtime_metadata(self):
        backend = ONNXRuntimeCPUEngine(self.model)
        self.assertEqual(backend.versions["execution_provider"], "CPUExecutionProvider")
        self.assertEqual(len(backend.infer(self.batch)), len(self.batch))

    def test_rejects_wrong_shape_and_nonfinite(self):
        backend = ONNXRuntimeCPUEngine(self.model)
        for data in ([[1.0, 2.0]], [[math.nan] * 6], [[math.inf] * 6], []):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    backend.infer(data)

    def test_benchmark_records_backend_tolerance_and_versions(self):
        report = benchmark([ReferenceEngine(self.model), ONNXRuntimeCPUEngine(self.model)], self.batch, warmup=0, repeats=2)
        item = report["engines"][1]
        self.assertEqual(item["tolerance"], {"atol": 1e-5, "rtol": 1e-4})
        self.assertEqual(item["runtime_versions"]["execution_provider"], "CPUExecutionProvider")
        self.assertTrue(item["correctness"]["passed"])
