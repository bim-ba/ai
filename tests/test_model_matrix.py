"""Offline unit tests for the opencode skill-load matrix (no network, no opencode)."""
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "model-matrix-check.py"
_spec = importlib.util.spec_from_file_location("model_matrix_check", SCRIPT)
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class TestGroundTruth(unittest.TestCase):
    def test_finds_known_repo_skills(self):
        names = mm.repo_skill_names(REPO)
        # a representative subset that must exist on disk
        for expected in ("setup", "creating-drift-logs", "clickhouse-query-best-practices"):
            self.assertIn(expected, names)
        self.assertGreaterEqual(len(names), 8)

    def test_empty_for_nonrepo(self):
        self.assertEqual(mm.repo_skill_names(REPO / "does-not-exist"), set())


class TestSelect(unittest.TestCase):
    def _payload(self):
        # already in popularity order; mix of free/paid and chat/non-chat
        return {"data": [
            {"id": "owl/top:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["tools", "temperature"]},
            {"id": "paid/second", "pricing": {"prompt": "0.001", "completion": "0"},
             "supported_parameters": ["tools"]},
            {"id": "safety/classifier:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": []},  # free but NOT a chat model (no tools)
            {"id": "qwen/third:free", "pricing": {"prompt": 0, "completion": 0},
             "supported_parameters": ["tools", "structured_outputs"]},
            {"id": "nv/fourth:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["tools"]},
        ]}

    def test_keeps_free_chat_models_and_preserves_order(self):
        self.assertEqual(
            mm.select_popular_free_chat_models(self._payload()),
            ["owl/top:free", "qwen/third:free", "nv/fourth:free"],
        )

    def test_excludes_non_chat_free_models(self):
        self.assertNotIn("safety/classifier:free", mm.select_popular_free_chat_models(self._payload()))

    def test_respects_n_cap(self):
        self.assertEqual(mm.select_popular_free_chat_models(self._payload(), n=1), ["owl/top:free"])


class TestExtract(unittest.TestCase):
    def test_plain_array(self):
        self.assertEqual(mm.extract_json_array('["a","b"]'), ["a", "b"])

    def test_array_with_prose_and_reminder(self):
        text = 'Here you go:\n["setup","data"]\nDrift-log check: none'
        self.assertEqual(mm.extract_json_array(text), ["setup", "data"])

    def test_fenced_array(self):
        self.assertEqual(mm.extract_json_array('```json\n["x"]\n```'), ["x"])

    def test_strips_ansi(self):
        self.assertEqual(mm.extract_json_array('\x1b[36m["a"]\x1b[0m'), ["a"])

    def test_newline_list_is_not_json(self):
        self.assertIsNone(mm.extract_json_array("setup\ndata\nusing-playwright"))


class TestValidate(unittest.TestCase):
    GT = {"setup", "data", "review"}

    def test_all_present_passes_extras_allowed(self):
        r = mm.validate_skills(["setup", "data", "review", "customize-opencode"], self.GT)
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["extra"], ["customize-opencode"])

    def test_missing_fails(self):
        r = mm.validate_skills(["setup", "data"], self.GT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"], ["review"])

    def test_none_reported_fails(self):
        r = mm.validate_skills(None, self.GT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"], sorted(self.GT))


class TestFormat(unittest.TestCase):
    def test_section_has_details_and_verdict(self):
        result = {"ok": False, "missing": ["setup"], "extra": [], "reported": ["data"]}
        out = mm.format_model_section("vendor/m:free", result, "\x1b[36mraw\x1b[0m output")
        self.assertIn("❌", out)
        self.assertIn("vendor/m:free", out)
        self.assertIn("**Missing repo skills:** setup", out)
        self.assertIn("<details><summary>raw agent output</summary>", out)
        self.assertIn("<details><summary>parsed skills</summary>", out)
        self.assertNotIn("\x1b[", out)  # ANSI stripped from raw block


if __name__ == "__main__":
    unittest.main()
