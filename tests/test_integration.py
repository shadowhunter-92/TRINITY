import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_three_layer_offline_composition(self):
        p = subprocess.run([sys.executable, "scripts/demo_end_to_end.py"], cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertEqual(data["input_signal_ids"], ["motor_temperature", "shaft_speed", "line_pressure"])
        self.assertTrue(data["runtime_comparison"]["passed"])
        self.assertEqual(data["verified_sensor_values"], [42.0, 1440.0, 12.34])

    def test_local_modbus_demo(self):
        p = subprocess.run([sys.executable, "scripts/demo_modbus_loopback.py"], cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)["passed"])
