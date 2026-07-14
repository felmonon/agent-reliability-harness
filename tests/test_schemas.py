"""Validate shipped JSON Schemas against every sample, fixture, and live output.

Requires the optional 'jsonschema' dev dependency; skipped when absent so the
core test suite stays dependency-free.
"""

import json
import unittest
from pathlib import Path

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAS_JSONSCHEMA = False

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / "schemas"
SAMPLES = REPO_ROOT / "samples"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed (dev extra)")
class TestSchemas(unittest.TestCase):
    def test_schemas_are_valid_draft_2020_12(self):
        for name in ("trace", "policy", "report"):
            schema = load(SCHEMAS / f"{name}.schema.json")
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_sample_traces_validate(self):
        schema = load(SCHEMAS / "trace.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        for path in sorted((SAMPLES / "traces").glob("*.json")):
            with self.subTest(trace=path.name):
                errors = list(validator.iter_errors(load(path)))
                self.assertEqual(errors, [], f"{path.name}: {[e.message for e in errors]}")

    def test_sample_policies_validate(self):
        schema = load(SCHEMAS / "policy.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        for path in sorted(SAMPLES.glob("policy*.json")):
            with self.subTest(policy=path.name):
                errors = list(validator.iter_errors(load(path)))
                self.assertEqual(errors, [], f"{path.name}: {[e.message for e in errors]}")

    def test_live_report_validates(self):
        from agent_reliability_harness.models import Policy, Trace
        from agent_reliability_harness.report import render_json
        from agent_reliability_harness.validator import validate_trace

        policy = Policy.from_dict(load(SAMPLES / "policy_trajectory.json"))
        reports = []
        for path in sorted((SAMPLES / "traces").glob("refund_*.json")):
            trace = Trace.from_dict(load(path))
            report = validate_trace(trace, policy)
            report.source_path = str(path)
            reports.append(report)
        document = render_json(reports)
        schema = load(SCHEMAS / "report.schema.json")
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(document))
        self.assertEqual(errors, [], [e.message for e in errors])

    def test_schema_rejects_bad_trace(self):
        schema = load(SCHEMAS / "trace.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        bad = {"trace_id": "t", "steps": [{"step_id": "s", "type": "bogus"}]}
        self.assertTrue(list(validator.iter_errors(bad)))


if __name__ == "__main__":
    unittest.main()
