"""Optional ONNX Runtime CPU execution of a locally constructed MLP graph.

No model files are downloaded or accepted from untrusted inputs. This module
is importable without ONNX, ONNX Runtime, or NumPy installed. On execution,
all three optional dependencies must be explicitly installed by the operator.

ONNX computations are float32; compare to float64 Python reference using
explicitly relaxed (but checked) tolerances. We benchmark conversion overhead
as part of infer(), not just the underlying runtime graph.
"""
from __future__ import annotations

import importlib

from trinitylab.compute.core import TinyMLP, _check_inputs


class MissingONNXDependencies(RuntimeError):
    """Raised when an optional ONNX module is not installed."""


def _load_dependencies():
    loaded = {}
    for name in ("numpy", "onnx", "onnxruntime"):
        try:
            loaded[name] = importlib.import_module(name)
        except ImportError as exc:
            raise MissingONNXDependencies(
                "ONNX CPU backend requires optional dependencies: "
                "pip install -e '.[compute-onnx]'"
            ) from exc
    return loaded["numpy"], loaded["onnx"], loaded["onnxruntime"]


def build_local_onnx_model(model: TinyMLP, onnx, np) -> bytes:
    """Export exactly MatMul+Add+ReLU+MatMul+Add, with no external tensors."""
    from onnx import TensorProto, helper, numpy_helper

    input_spec = helper.make_tensor_value_info(
        "features", TensorProto.FLOAT, ["batch", model.input_dim]
    )
    output_spec = helper.make_tensor_value_info(
        "predictions", TensorProto.FLOAT, ["batch", model.output_dim]
    )
    tensors = {
        "w1": np.asarray(model.w1, dtype=np.float32),
        "b1": np.asarray(model.b1, dtype=np.float32),
        "w2": np.asarray(model.w2, dtype=np.float32),
        "b2": np.asarray(model.b2, dtype=np.float32),
    }
    initializers = [numpy_helper.from_array(value, name) for name, value in tensors.items()]
    nodes = [
        helper.make_node("MatMul", ["features", "w1"], ["hidden_product"]),
        helper.make_node("Add", ["hidden_product", "b1"], ["hidden_biased"]),
        helper.make_node("Relu", ["hidden_biased"], ["hidden"]),
        helper.make_node("MatMul", ["hidden", "w2"], ["output_product"]),
        helper.make_node("Add", ["output_product", "b2"], ["predictions"]),
    ]
    graph = helper.make_graph(
        nodes, "trinity_local_tiny_mlp", [input_spec], [output_spec], initializer=initializers
    )
    exported = helper.make_model(
        graph, producer_name="trinity-lab", opset_imports=[helper.make_operatorsetid("", 13)]
    )
    # A portable IR version supported by a broad range of ORT releases.
    exported.ir_version = 8
    onnx.checker.check_model(exported)
    return exported.SerializeToString()


class ONNXRuntimeCPUEngine:
    """Bounded, locally synthesized ONNX graph; CPUExecutionProvider only."""

    name = "onnxruntime_cpu_float32"
    atol = 1e-5
    rtol = 1e-4

    def __init__(self, model: TinyMLP):
        np, onnx, ort = _load_dependencies()
        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 1
        session_options.inter_op_num_threads = 1
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        blob = build_local_onnx_model(model, onnx, np)
        self.session = ort.InferenceSession(
            blob, sess_options=session_options, providers=["CPUExecutionProvider"]
        )
        if "CPUExecutionProvider" not in self.session.get_providers():
            raise RuntimeError("ONNX Runtime CPU execution provider is unavailable")
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise RuntimeError("Unexpected ONNX graph interface")
        if inputs[0].name != "features" or outputs[0].name != "predictions":
            raise RuntimeError("Unexpected ONNX graph input/output names")
        self.model = model
        self.np = np
        self.versions = {
            "numpy": np.__version__, "onnx": onnx.__version__,
            "onnxruntime": ort.__version__, "execution_provider": "CPUExecutionProvider",
            "onnx_opset": 13, "onnx_ir_version": 8,
        }

    def infer(self, batch: list[list[float]]) -> list[list[float]]:
        _check_inputs(self.model, batch)
        data = self.np.asarray(batch, dtype=self.np.float32)
        if data.ndim != 2 or data.shape[1] != self.model.input_dim:
            raise ValueError("Unexpected input tensor shape")
        result = self.session.run(["predictions"], {"features": data})[0]
        if result.shape != (len(batch), self.model.output_dim):
            raise RuntimeError("Unexpected output tensor shape")
        if not bool(self.np.isfinite(result).all()):
            raise RuntimeError("ONNX runtime emitted a nonfinite output")
        return result.tolist()
