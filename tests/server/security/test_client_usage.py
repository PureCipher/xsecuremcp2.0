from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from purecipher.client_usage import estimated_tokens, summarize_token_usage


def row(action="tool_called", metadata=None, age=1, resource="time_current"):
    return SimpleNamespace(
        action=action,
        resource_id=resource,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=age),
        metadata=metadata,
    )


def test_persisted_counts_are_aggregated_once_and_missing_usage_is_explicit():
    records = [
        row(metadata={"input_tokens": 6, "output_tokens": 34}),
        row("execution_receipt", {"input_tokens": 6, "output_tokens": 34}),
        row(metadata={"input_tokens": 999, "output_tokens": 999}, age=25),
        row(),
        row(metadata={"input_tokens": 2, "output_tokens": 0}),
    ]
    result = summarize_token_usage(records, datetime.now(timezone.utc))
    assert result["input_tokens"] == 8
    assert result["output_tokens"] == 34
    assert result["total_tokens"] == 42
    assert result["calls_with_usage"] == 2
    assert result["calls_without_usage"] == 1
    assert result["measurement"] == "estimated"
    assert estimated_tokens(records[1]) is None


def test_unknown_invalid_and_empty_are_distinct():
    now = datetime.now(timezone.utc)
    assert summarize_token_usage([], now)["total_tokens"] == 0
    assert summarize_token_usage([row()], now)["total_tokens"] is None
    for value in [-1, True, "3", 1.5, None]:
        assert (
            estimated_tokens(row(metadata={"input_tokens": value, "output_tokens": 5}))
            is None
        )
    zero_usage = estimated_tokens(row(metadata={"input_tokens": 0, "output_tokens": 0}))
    assert zero_usage is not None
    assert zero_usage["total_tokens"] == 0
    assert (
        estimated_tokens(
            row(
                metadata={"input_tokens": 4, "output_tokens": 5},
                resource="__list_tools__",
            )
        )
        is None
    )
    assert summarize_token_usage([row(age=-1)], now)["calls_without_usage"] == 0
    assert summarize_token_usage([row()] * 1000, now)["window_may_be_truncated"]


def test_governance_projects_only_safe_usage_and_handles_unavailable_ledger(
    monkeypatch,
):
    from purecipher.registry import PureCipherRegistry

    registry = PureCipherRegistry(signing_secret="test-token-usage-secret")
    registry.register_client(
        display_name="Usage QA",
        owner_publisher_id="acme",
        slug="usage-qa",
        kind="agent",
    )
    measured = row(
        metadata={"input_tokens": 6, "output_tokens": 34, "secret": "never expose"}
    )

    def records(**kwargs):
        assert kwargs == {"actor_id": "usage-qa", "limit": 1000}
        return [measured]

    monkeypatch.setattr(
        registry, "_ledger_or_none", lambda: SimpleNamespace(get_records=records)
    )
    response = registry.get_client_governance("usage-qa")
    assert response["activity"]["token_usage_24h"]["total_tokens"] == 40
    event = response["ledger"]["recent_records"][0]
    assert event["token_usage"]["total_tokens"] == 40
    assert "metadata" not in event
    public = registry.get_client_governance("usage-qa", sanitize_for_public=True)
    assert "token_usage_24h" not in public["activity"]
    assert "token_usage" not in public["ledger"]["recent_records"][0]
    monkeypatch.setattr(registry, "_ledger_or_none", lambda: None)
    assert (
        registry.get_client_governance("usage-qa")["activity"]["token_usage_24h"]
        is None
    )

    def broken(**kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(
        registry, "_ledger_or_none", lambda: SimpleNamespace(get_records=broken)
    )
    assert (
        registry.get_client_governance("usage-qa")["activity"]["token_usage_24h"]
        is None
    )
