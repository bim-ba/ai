"""String-assertion guards for workflow files (no YAML dep)."""
import unittest
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class TestAdvisorySmoke(unittest.TestCase):
    def test_renamed_from_opencode_smoke(self):
        self.assertTrue((WF / "advisory-smoke.yml").exists())
        self.assertFalse((WF / "opencode-smoke.yml").exists())

    def test_dead_model_gone(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertNotIn("deepseek-r1", txt)

    def test_has_both_jobs(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("model-matrix", txt)
        self.assertIn("opencode", txt)

    def test_matrix_job_runs_the_script(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/model-matrix-check.py", txt)


if __name__ == "__main__":
    unittest.main()
