"""BehavioralObservation v1 schema and adapter contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from fastmcp.server.security.reflexive import (
    BEHAVIORAL_OBSERVATION_SCHEMA_VERSION,
    BehavioralAnalyzer,
    BehavioralMetric,
    BehavioralObservation,
)

SCHEMA_PATH = (
    Path(__file__).parents[3]
    / "docs"
    / "public"
    / "schemas"
    / "behavioral-observation"
    / "v1.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_v1_schema_is_valid_and_matches_runtime_metrics():
    schema = _schema()

    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["schema_version"]["const"] == (
        BEHAVIORAL_OBSERVATION_SCHEMA_VERSION
    )
    assert set(schema["properties"]["metric_name"]["enum"]) == {
        metric.value for metric in BehavioralMetric
    }


def test_observation_round_trips_and_validates_against_public_schema():
    observation = BehavioralObservation(
        actor_id="deployment-agent",
        metric_name=BehavioralMetric.LATENCY_MS,
        value=42,
        metadata={"operation": "call_tool"},
    )

    payload = observation.to_dict()
    Draft202012Validator(_schema()).validate(payload)
    assert BehavioralObservation.from_dict(payload) == observation
    assert payload == {
        "schema_version": "1.0",
        "actor_id": "deployment-agent",
        "metric_name": "latency_ms",
        "value": 42.0,
        "metadata": {"operation": "call_tool"},
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "actor_id": "agent",
            "metric_name": "latency_ms",
            "value": 1,
        },
        {
            "schema_version": "2.0",
            "actor_id": "agent",
            "metric_name": "latency_ms",
            "value": 1,
        },
        {
            "schema_version": "1.0",
            "actor_id": "agent",
            "metric_name": "custom_metric",
            "value": 1,
        },
        {
            "schema_version": "1.0",
            "actor_id": "agent",
            "metric_name": "error_rate",
            "value": 1.1,
        },
        {
            "schema_version": "1.0",
            "actor_id": "agent",
            "metric_name": "latency_ms",
            "value": 1,
            "unexpected": True,
        },
    ],
)
def test_public_schema_rejects_invalid_observations(payload):
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(payload)


def test_runtime_model_rejects_invalid_values_and_shapes():
    with pytest.raises(ValueError, match="non-empty"):
        BehavioralObservation(
            actor_id=" ",
            metric_name=BehavioralMetric.LATENCY_MS,
            value=1,
        )
    with pytest.raises(ValueError, match="finite and non-negative"):
        BehavioralObservation(
            actor_id="agent",
            metric_name=BehavioralMetric.LATENCY_MS,
            value=float("nan"),
        )
    with pytest.raises(ValueError, match="between 0 and 1"):
        BehavioralObservation(
            actor_id="agent",
            metric_name=BehavioralMetric.ERROR_RATE,
            value=1.1,
        )
    with pytest.raises(ValueError, match="Unknown BehavioralObservation field"):
        BehavioralObservation.from_dict(
            {
                "schema_version": "1.0",
                "actor_id": "agent",
                "metric_name": "latency_ms",
                "value": 1,
                "unexpected": True,
            }
        )


def test_observe_v1_delegates_to_existing_baseline_and_metadata_behavior():
    analyzer = BehavioralAnalyzer(min_samples=5)
    for value in [10.0, 10.0, 10.0, 11.0, 9.0]:
        analyzer.observe_v1(
            BehavioralObservation(
                actor_id="agent",
                metric_name=BehavioralMetric.CALLS_PER_MINUTE,
                value=value,
            )
        )

    events = analyzer.observe_v1(
        BehavioralObservation(
            actor_id="agent",
            metric_name=BehavioralMetric.CALLS_PER_MINUTE,
            value=100,
            metadata={"operation": "call_tool"},
        )
    )

    assert len(events) == 1
    assert events[0].metadata == {
        "metric_name": "calls_per_minute",
        "operation": "call_tool",
    }
