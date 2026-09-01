"""Security regressions for constrained policy and consent expressions."""

from __future__ import annotations

from typing import Any

import pytest

from fastmcp.server.security.consent.models import ConsentCondition
from fastmcp.server.security.expression import (
    SafeExpressionError,
    evaluate_boolean_expression,
    evaluate_expression,
)
from fastmcp.server.security.policy.invariants import (
    ExpressionInvariantVerifier,
    Invariant,
)


def test_evaluator_supports_data_expressions_and_comprehensions():
    context = {
        "request": {"role": "admin", "scores": [2, 4, 6]},
        "minimum": 2,
    }

    result = evaluate_boolean_expression(
        "request.role == 'admin' and "
        "all(score >= minimum for score in request['scores'])",
        context,
    )

    assert result is True


def test_evaluator_supports_bounded_arithmetic_and_collections():
    result = evaluate_expression(
        "sum(values) / len(values) if values else 0",
        {"values": [2, 4, 6]},
    )

    assert result == 4


@pytest.mark.parametrize(
    ("expression", "context", "expected"),
    [
        ("request.role", {"request": {"role": "admin"}}, "admin"),
        ("items[1:4:2]", {"items": [0, 1, 2, 3, 4]}, [1, 3]),
        ("1 + 4 - 2", {}, 3),
        ("7 // 2", {}, 3),
        ("7 % 4", {}, 3),
        ("abs(-4)", {}, 4),
        ("min(values) + max(values)", {"values": [3, 1, 4]}, 5),
        ("3 not in values", {"values": [1, 2]}, True),
        ("None is None", {}, True),
        ("isinstance(value, (int, float))", {"value": 3}, True),
        ("str(value)", {"value": 3}, "3"),
        ("int(value)", {"value": "3"}, 3),
        ("float(value)", {"value": "3.5"}, 3.5),
        ("bool(value)", {"value": []}, False),
        ("tuple(values)", {"values": [1, 2]}, (1, 2)),
        ("set(values)", {"values": [1, 1]}, {1}),
        ("dict(pairs)", {"pairs": [["a", 1]]}, {"a": 1}),
        ("[x * 2 for x in values if x > 1]", {"values": [1, 2, 3]}, [4, 6]),
        ("{x for x in values}", {"values": [1, 1, 2]}, {1, 2}),
        (
            "{key: value for key, value in pairs}",
            {"pairs": [["a", 1], ["b", 2]]},
            {"a": 1, "b": 2},
        ),
    ],
)
def test_evaluator_supported_expression_families(
    expression: str,
    context: dict[str, Any],
    expected: Any,
):
    assert evaluate_expression(expression, context) == expected


def test_context_callable_cannot_be_invoked():
    called = False

    def dangerous() -> bool:
        nonlocal called
        called = True
        return True

    with pytest.raises(SafeExpressionError, match="not permitted"):
        evaluate_boolean_expression("dangerous()", {"dangerous": dangerous})

    assert called is False


def test_context_cannot_replace_allowlisted_function():
    called = False

    def dangerous(_: object) -> int:
        nonlocal called
        called = True
        return 0

    result = evaluate_boolean_expression(
        "len(items) == 2",
        {"items": [1, 2], "len": dangerous},
    )

    assert result is True
    assert called is False


def test_object_attributes_are_not_accessed():
    accessed = False

    class Dangerous:
        @property
        def value(self) -> bool:
            nonlocal accessed
            accessed = True
            return True

    with pytest.raises(SafeExpressionError, match="mapping keys"):
        evaluate_boolean_expression("dangerous.value", {"dangerous": Dangerous()})

    assert accessed is False


def test_custom_mapping_context_is_not_accessed():
    accessed = False

    class DangerousDict(dict[str, object]):
        def __iter__(self):
            nonlocal accessed
            accessed = True
            return super().__iter__()

    with pytest.raises(SafeExpressionError, match="built-in dictionary"):
        evaluate_boolean_expression("True", DangerousDict())

    assert accessed is False


def test_custom_context_key_is_rejected_before_lookup():
    compared = False

    class DangerousKey:
        def __hash__(self) -> int:
            return hash("value")

        def __eq__(self, other: object) -> bool:
            nonlocal compared
            compared = True
            return other == "value"

    context = {DangerousKey(): True}

    with pytest.raises(SafeExpressionError, match="names must be strings"):
        evaluate_boolean_expression(
            "value",
            context,  # ty: ignore[invalid-argument-type]
        )

    assert compared is False


def test_oversized_context_is_rejected():
    context = {f"name_{index}": index for index in range(257)}

    with pytest.raises(SafeExpressionError, match="too many names"):
        evaluate_boolean_expression("True", context)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "(1).__class__.__mro__[1].__subclasses__()",
        "getattr(target, 'value')",
        "target.copy()",
        "dict(value=1)",
        "{**target}",
        "[*target]",
        "(value := 1)",
        "f'{target}'",
        "'value=%s' % target",
        "2 ** 8",
        "lambda: True",
    ],
)
def test_python_escape_syntax_is_rejected(expression: str):
    with pytest.raises(SafeExpressionError):
        evaluate_expression(expression, {"target": object()})


def test_set_literal_rejects_custom_hash_without_invoking_it():
    hashed = False

    class Dangerous:
        def __hash__(self) -> int:
            nonlocal hashed
            hashed = True
            return 1

    with pytest.raises(SafeExpressionError, match="not data-safe"):
        evaluate_expression("{dangerous}", {"dangerous": Dangerous()})

    assert hashed is False


def test_comparison_rejects_custom_equality_without_invoking_it():
    compared = False

    class Dangerous:
        def __eq__(self, other: object) -> bool:
            nonlocal compared
            compared = True
            return other is self

    with pytest.raises(SafeExpressionError, match="not data-safe"):
        evaluate_expression("dangerous == 1", {"dangerous": Dangerous()})

    assert compared is False


def test_expression_result_size_is_bounded_before_allocation():
    with pytest.raises(SafeExpressionError, match="too large"):
        evaluate_expression("'x' * 100001", {})


def test_expression_rejects_oversized_context_before_concatenation():
    with pytest.raises(SafeExpressionError, match="too large"):
        evaluate_expression("value + 'x'", {"value": "x" * 100001})


def test_expression_rejects_oversized_slice_from_context():
    with pytest.raises(SafeExpressionError, match="too large"):
        evaluate_expression("values[:]", {"values": list(range(10001))})


def test_expression_rejects_non_data_result():
    with pytest.raises(SafeExpressionError, match="not data-safe"):
        evaluate_expression("dangerous", {"dangerous": object()})


def test_expression_normalizes_arithmetic_errors():
    with pytest.raises(SafeExpressionError, match="evaluation failed"):
        evaluate_expression("1 / 0", {})


def test_expression_length_is_bounded():
    with pytest.raises(SafeExpressionError, match="maximum length"):
        evaluate_expression("True" + " " * 4093, {})


def test_expression_ast_complexity_is_bounded():
    expression = " + ".join(["1"] * 130)

    with pytest.raises(SafeExpressionError, match="too complex"):
        evaluate_expression(expression, {})


def test_expression_nesting_is_bounded():
    expression = "[" * 40 + "1" + "]" * 40

    with pytest.raises(SafeExpressionError, match="nesting is too deep"):
        evaluate_expression(expression, {})


def test_expression_integer_size_is_bounded():
    with pytest.raises(SafeExpressionError, match="integer result is too large"):
        evaluate_expression(str(2**4096), {})


def test_invariant_verifier_fails_closed_on_escape_attempt():
    invariant = Invariant(
        id="no-code-execution",
        description="Expressions must remain data-only",
        expression="(1).__class__.__subclasses__()",
    )

    result = ExpressionInvariantVerifier().verify(invariant, {})

    assert result.satisfied is False
    assert result.counter_example is not None
    assert "error" in result.counter_example


def test_consent_condition_fails_closed_without_calling_context_function():
    called = False

    def dangerous() -> bool:
        nonlocal called
        called = True
        return True

    condition = ConsentCondition(expression="dangerous()")

    assert condition.evaluate({"dangerous": dangerous}) is False
    assert called is False
