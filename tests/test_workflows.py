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

    def test_single_skill_matrix_job(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        # Consolidated to one opencode-backed job (pin the job key, not a substring).
        self.assertIn("  skill-matrix:", txt)
        self.assertNotIn("  model-matrix:", txt)
        self.assertNotIn("  opencode:", txt)

    def test_matrix_job_runs_the_script_and_tees_summary(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/model-matrix-check.py", txt)
        # tee so the table shows in both the log and the step summary
        self.assertIn('tee -a "$GITHUB_STEP_SUMMARY"', txt)

    def test_installs_opencode(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("opencode.ai/install", txt)


class TestReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        self.txt = (WF / "release.yml").read_text(encoding="utf-8")

    def test_uses_oidc(self):
        self.assertIn("id-token: write", self.txt)

    def test_scoped_to_release_environment(self):
        self.assertIn("environment: release", self.txt)

    def test_publishes_with_provenance(self):
        self.assertIn("--provenance", self.txt)

    def test_no_long_lived_token(self):
        self.assertNotIn("NPM_TOKEN", self.txt)
        self.assertNotIn("NPM_ACCESS_TOKEN", self.txt)
        self.assertNotIn("NODE_AUTH_TOKEN", self.txt)


if __name__ == "__main__":
    unittest.main()
