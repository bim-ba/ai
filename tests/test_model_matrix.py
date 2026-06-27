"""Offline unit tests for the free-model matrix probe (no network)."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model-matrix-check.py"
_spec = importlib.util.spec_from_file_location("model_matrix_check", SCRIPT)
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class TestSelect(unittest.TestCase):
    def _payload(self):
        return {"data": [
            {"id": "b/struct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["structured_outputs", "response_format"]},
            {"id": "a/struct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["structured_outputs"]},
            {"id": "c/nostruct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["tools"]},
            {"id": "d/paid-struct", "pricing": {"prompt": "0.001", "completion": "0"},
             "supported_parameters": ["structured_outputs"]},
        ]}

    def test_selects_only_free_and_structured_sorted(self):
        self.assertEqual(
            mm.select_free_structured_models(self._payload()),
            ["a/struct:free", "b/struct:free"],
        )

    def test_respects_n_cap(self):
        payload = {"data": [
            {"id": f"m{i}:free", "pricing": {"prompt": 0, "completion": 0},
             "supported_parameters": ["structured_outputs"]} for i in range(10)
        ]}
        self.assertEqual(len(mm.select_free_structured_models(payload, n=3)), 3)

    def test_empty_when_none_match(self):
        self.assertEqual(mm.select_free_structured_models({"data": []}), [])


class TestValidate(unittest.TestCase):
    def test_valid_object_passes(self):
        obj = {"project": "ai", "skills": ["a", "b"], "agent_targets": ["claude"]}
        self.assertEqual(mm.validate_against_schema(obj, mm.PROBE_SCHEMA), [])

    def test_missing_required_key_fails(self):
        errs = mm.validate_against_schema({"project": "ai", "skills": ["a"]}, mm.PROBE_SCHEMA)
        self.assertTrue(any("agent_targets" in e for e in errs))

    def test_wrong_type_fails(self):
        obj = {"project": "ai", "skills": "not-a-list", "agent_targets": []}
        errs = mm.validate_against_schema(obj, mm.PROBE_SCHEMA)
        self.assertTrue(any("skills" in e for e in errs))

    def test_non_object_root_fails(self):
        self.assertTrue(mm.validate_against_schema(["x"], mm.PROBE_SCHEMA))

    def test_additional_property_fails(self):
        obj = {"project": "ai", "skills": ["a"], "agent_targets": ["claude"], "extra": 1}
        errs = mm.validate_against_schema(obj, mm.PROBE_SCHEMA)
        self.assertTrue(any("extra" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
