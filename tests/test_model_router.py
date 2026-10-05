import unittest
from unittest.mock import patch

from support import install_dependency_stubs

install_dependency_stubs()

from gateway_mcp.services.model_router import (  # noqa: E402
    ModelRoutingError,
    apply_model_route,
    resolve_model_route,
)


CONFIG = {
    "profiles": {
        "cheap": {
            "model_env": "TEST_CHEAP_MODEL",
            "max_output_tokens": 100,
        },
    },
    "workflows": {
        "outreach": {
            "stages": {
                "classify": {"profile": "cheap", "autonomous_allowed": True},
                "draft": {
                    "profile": "cheap",
                    "autonomous_allowed": False,
                    "human_approval_required": True,
                },
                "send": {"deterministic": True, "autonomous_allowed": False},
            }
        }
    },
}


class ModelRouterTests(unittest.TestCase):
    def test_resolves_env_model_and_caps_tokens(self) -> None:
        with patch.dict("os.environ", {"TEST_CHEAP_MODEL": "provider/fast"}):
            route = resolve_model_route(
                "outreach", "classify", autonomous=True, config=CONFIG
            )
        payload = {"max_output_tokens": 999}
        apply_model_route(payload, route, api="responses")
        self.assertEqual(route.model, "provider/fast")
        self.assertEqual(payload["model"], "provider/fast")
        self.assertEqual(payload["max_output_tokens"], 100)

    def test_blocks_autonomous_human_gate(self) -> None:
        with patch.dict("os.environ", {"TEST_CHEAP_MODEL": "provider/fast"}):
            with self.assertRaisesRegex(ModelRoutingError, "not allowed"):
                resolve_model_route(
                    "outreach", "draft", autonomous=True, config=CONFIG
                )

    def test_rejects_deterministic_stage(self) -> None:
        with self.assertRaisesRegex(ModelRoutingError, "must not invoke an LLM"):
            resolve_model_route("outreach", "send", config=CONFIG)

    def test_fails_closed_when_model_is_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ModelRoutingError, "not configured"):
                resolve_model_route("outreach", "classify", config=CONFIG)


if __name__ == "__main__":
    unittest.main()
