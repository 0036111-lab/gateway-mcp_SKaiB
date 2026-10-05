from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from gateway_mcp.config import model_routing_file, read_json


class ModelRoutingError(ValueError):
    """Raised when a workflow stage cannot be routed safely."""


@dataclass(frozen=True)
class ModelRoute:
    workflow: str
    stage: str
    profile: str
    model: str
    max_output_tokens: int
    autonomous_allowed: bool
    human_approval_required: bool


def resolve_model_route(
    workflow: str,
    stage: str,
    *,
    autonomous: bool = False,
    config: dict[str, Any] | None = None,
) -> ModelRoute:
    workflow_key = workflow.strip()
    stage_key = stage.strip()
    if not workflow_key or not stage_key:
        raise ModelRoutingError("workflow and stage are required for model routing")

    routing = config if config is not None else read_json(model_routing_file(), {})
    workflows = routing.get("workflows") if isinstance(routing, dict) else None
    workflow_config = workflows.get(workflow_key) if isinstance(workflows, dict) else None
    if not isinstance(workflow_config, dict):
        raise ModelRoutingError(f"unknown model-routing workflow: {workflow_key}")

    stages = workflow_config.get("stages")
    stage_config = stages.get(stage_key) if isinstance(stages, dict) else None
    if not isinstance(stage_config, dict):
        raise ModelRoutingError(
            f"unknown model-routing stage: {workflow_key}/{stage_key}"
        )
    if bool(stage_config.get("deterministic")):
        raise ModelRoutingError(
            f"stage {workflow_key}/{stage_key} must not invoke an LLM"
        )

    profile_key = str(stage_config.get("profile") or "").strip()
    profiles = routing.get("profiles")
    profile = profiles.get(profile_key) if isinstance(profiles, dict) else None
    if not profile_key or not isinstance(profile, dict):
        raise ModelRoutingError(
            f"model profile is not configured for {workflow_key}/{stage_key}"
        )

    autonomous_allowed = bool(stage_config.get("autonomous_allowed", False))
    human_approval_required = bool(stage_config.get("human_approval_required", False))
    if autonomous and (not autonomous_allowed or human_approval_required):
        raise ModelRoutingError(
            f"autonomous execution is not allowed for {workflow_key}/{stage_key}"
        )

    model = str(profile.get("model") or "").strip()
    model_env = str(profile.get("model_env") or "").strip()
    if model_env:
        model = os.getenv(model_env, model).strip()
    if not model:
        raise ModelRoutingError(
            f"model profile {profile_key} is not configured; set {model_env or 'model'}"
        )

    max_output_tokens = int(profile.get("max_output_tokens") or 0)
    if max_output_tokens < 1:
        raise ModelRoutingError(
            f"model profile {profile_key} must define max_output_tokens"
        )
    return ModelRoute(
        workflow=workflow_key,
        stage=stage_key,
        profile=profile_key,
        model=model,
        max_output_tokens=max_output_tokens,
        autonomous_allowed=autonomous_allowed,
        human_approval_required=human_approval_required,
    )


def apply_model_route(payload: dict[str, Any], route: ModelRoute, *, api: str) -> None:
    payload["model"] = route.model
    token_key = "max_tokens" if api == "chat" else "max_output_tokens"
    requested = payload.get(token_key)
    if requested is None:
        payload[token_key] = route.max_output_tokens
        return
    try:
        payload[token_key] = min(int(requested), route.max_output_tokens)
    except (TypeError, ValueError) as exc:
        raise ModelRoutingError(f"{token_key} must be an integer") from exc
