import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, module, *args, exit_code=0):
        proc = subprocess.run([sys.executable, "-m", module, *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, exit_code, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_compute_cli(self):
        result = self.run_cli("trinitylab.compute", "benchmark", "--input-dim", "8", "--hidden-dim", "8", "--batch", "2", "--repeats", "2")
        self.assertEqual(result["project"], "trinity_compute")

    def test_industrial_cli(self):
        result = self.run_cli("trinitylab.industrial", "drift", "--old", "fixtures/industrial/profile_v1.json", "--new", "fixtures/industrial/profile_v2.json")
        self.assertTrue(result["drift_detected"])

    def test_schema_cli_exit_status(self):
        self.run_cli("trinitylab.data", "schema-diff", "--old", "fixtures/data/schema_v1.json", "--new", "fixtures/data/schema_v2_breaking.json", exit_code=1)

    def test_report_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            result = self.run_cli("trinitylab.data", "benchmark", "--rows", "30", "--repeats", "2", "--output", str(path))
            self.assertEqual(result, json.loads(path.read_text()))

    def test_modbus_requires_enable_flag(self):
        proc = subprocess.run([sys.executable, "-m", "trinitylab.industrial", "modbus-read"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Network disabled", proc.stderr)
