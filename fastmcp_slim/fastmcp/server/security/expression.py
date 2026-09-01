"""Constrained expression evaluation for SecureMCP policy data.

The evaluator intentionally implements a small, data-oriented subset of
Python expressions. It never calls ``eval`` or ``compile`` and never invokes
attributes, methods, or callables supplied through the evaluation context.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Iterable
from typing import Any

_MAX_EXPRESSION_LENGTH = 4_096
_MAX_AST_NODES = 256
_MAX_EVALUATION_STEPS = 50_000
_MAX_CONTEXT_NAMES = 256
_MAX_COLLECTION_ITEMS = 10_000
_MAX_RESULT_SIZE = 100_000
_MAX_INTEGER_BITS = 4_096
_MAX_NESTING_DEPTH = 32

_SAFE_TYPES: dict[str, type[Any]] = {
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "list": list,
    "set": set,
    "str": str,
    "tuple": tuple,
}


class SafeExpressionError(ValueError):
    """Raised when an expression uses unsupported or unsafe behavior."""


class _Evaluator:
    def __init__(self, context: dict[str, Any]) -> None:
        if type(context) is not dict:
            raise SafeExpressionError(
                "Expression context must be a built-in dictionary"
            )
        if len(context) > _MAX_CONTEXT_NAMES:
            raise SafeExpressionError("Expression context contains too many names")
        if any(type(name) is not str for name in context):
            raise SafeExpressionError("Expression context names must be strings")
        self._context = context.copy()
        self._steps = 0

    def evaluate(self, expression: str) -> Any:
        if len(expression) > _MAX_EXPRESSION_LENGTH:
            raise SafeExpressionError("Expression exceeds the maximum length")
        try:
            tree = ast.parse(expression, mode="eval")
        except (RecursionError, SyntaxError) as exc:
            raise SafeExpressionError("Expression contains invalid syntax") from exc
        if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
            raise SafeExpressionError("Expression is too complex")
        try:
            result = self._evaluate_node(tree.body, dict(self._context), depth=0)
            _require_safe_value(result)
            return result
        except SafeExpressionError:
            raise
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            raise SafeExpressionError("Expression evaluation failed") from exc

    def _tick(self, depth: int) -> None:
        self._steps += 1
        if self._steps > _MAX_EVALUATION_STEPS:
            raise SafeExpressionError("Expression exceeded its evaluation budget")
        if depth > _MAX_NESTING_DEPTH:
            raise SafeExpressionError("Expression nesting is too deep")

    def _evaluate_node(
        self,
        node: ast.AST,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        self._tick(depth)

        if isinstance(node, ast.Constant):
            return self._constant(node.value)
        if isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            if node.id in _SAFE_TYPES:
                return _SAFE_TYPES[node.id]
            raise SafeExpressionError(f"Unknown expression name: {node.id}")
        if isinstance(node, ast.List):
            return self._collection(node.elts, scope, depth=depth, kind=list)
        if isinstance(node, ast.Tuple):
            return self._collection(node.elts, scope, depth=depth, kind=tuple)
        if isinstance(node, ast.Set):
            return self._collection(node.elts, scope, depth=depth, kind=set)
        if isinstance(node, ast.Dict):
            return self._dictionary(node, scope, depth=depth)
        if isinstance(node, ast.BoolOp):
            return self._boolean_operation(node, scope, depth=depth)
        if isinstance(node, ast.UnaryOp):
            return self._unary_operation(node, scope, depth=depth)
        if isinstance(node, ast.BinOp):
            return self._binary_operation(node, scope, depth=depth)
        if isinstance(node, ast.Compare):
            return self._comparison(node, scope, depth=depth)
        if isinstance(node, ast.IfExp):
            branch = (
                node.body
                if self._truth(self._evaluate_node(node.test, scope, depth=depth + 1))
                else node.orelse
            )
            return self._evaluate_node(branch, scope, depth=depth + 1)
        if isinstance(node, ast.Subscript):
            return self._subscript(node, scope, depth=depth)
        if isinstance(node, ast.Attribute):
            return self._mapping_attribute(node, scope, depth=depth)
        if isinstance(node, ast.Call):
            return self._call(node, scope, depth=depth)
        if isinstance(node, ast.GeneratorExp | ast.ListComp | ast.SetComp):
            values = self._comprehension_values(node, scope, depth=depth)
            if isinstance(node, ast.SetComp):
                for value in values:
                    _require_safe_hashable(value)
                return set(values)
            return values
        if isinstance(node, ast.DictComp):
            return self._dictionary_comprehension(node, scope, depth=depth)

        raise SafeExpressionError(
            f"Unsupported expression syntax: {type(node).__name__}"
        )

    @staticmethod
    def _constant(value: Any) -> Any:
        if type(value) not in {type(None), bool, int, float, str}:
            raise SafeExpressionError("Expression contains an unsupported constant")
        _check_result_size(value)
        return value

    def _collection(
        self,
        elements: list[ast.expr],
        scope: dict[str, Any],
        *,
        depth: int,
        kind: type[list[Any]] | type[tuple[Any, ...]] | type[set[Any]],
    ) -> list[Any] | tuple[Any, ...] | set[Any]:
        if len(elements) > _MAX_COLLECTION_ITEMS:
            raise SafeExpressionError("Expression collection is too large")
        values = [
            self._evaluate_node(item, scope, depth=depth + 1) for item in elements
        ]
        if kind is set:
            for value in values:
                _require_safe_hashable(value)
        return kind(values)

    def _dictionary(
        self,
        node: ast.Dict,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> dict[Any, Any]:
        if len(node.keys) > _MAX_COLLECTION_ITEMS:
            raise SafeExpressionError("Expression collection is too large")
        result: dict[Any, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            if key_node is None:
                raise SafeExpressionError("Dictionary unpacking is not supported")
            key = self._evaluate_node(key_node, scope, depth=depth + 1)
            _require_safe_hashable(key)
            result[key] = self._evaluate_node(value_node, scope, depth=depth + 1)
        return result

    def _boolean_operation(
        self,
        node: ast.BoolOp,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        if isinstance(node.op, ast.And):
            result: Any = True
            for value_node in node.values:
                result = self._evaluate_node(value_node, scope, depth=depth + 1)
                if not self._truth(result):
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value_node in node.values:
                result = self._evaluate_node(value_node, scope, depth=depth + 1)
                if self._truth(result):
                    return result
            return result
        raise SafeExpressionError("Unsupported boolean operator")

    def _unary_operation(
        self,
        node: ast.UnaryOp,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        value = self._evaluate_node(node.operand, scope, depth=depth + 1)
        if isinstance(node.op, ast.Not):
            return not self._truth(value)
        _require_number(value)
        if isinstance(node.op, ast.USub):
            return _checked_number(-value)
        if isinstance(node.op, ast.UAdd):
            return _checked_number(+value)
        raise SafeExpressionError("Unsupported unary operator")

    def _binary_operation(
        self,
        node: ast.BinOp,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        left = self._evaluate_node(node.left, scope, depth=depth + 1)
        right = self._evaluate_node(node.right, scope, depth=depth + 1)

        if isinstance(node.op, ast.Add):
            if _both_numbers(left, right):
                return _checked_number(operator.add(left, right))
            if type(left) is type(right) and type(left) in {str, list, tuple}:
                return _safe_add(left, right)
        elif isinstance(node.op, ast.Sub) and _both_numbers(left, right):
            return _checked_number(operator.sub(left, right))
        elif isinstance(node.op, ast.Mult):
            return _safe_multiply(left, right)
        elif isinstance(node.op, ast.Div) and _both_numbers(left, right):
            return _checked_number(operator.truediv(left, right))
        elif isinstance(node.op, ast.FloorDiv) and _both_numbers(left, right):
            return _checked_number(operator.floordiv(left, right))
        elif isinstance(node.op, ast.Mod):
            if _both_numbers(left, right):
                return _checked_number(operator.mod(left, right))

        raise SafeExpressionError(
            f"Unsupported binary operator: {type(node.op).__name__}"
        )

    def _comparison(
        self,
        node: ast.Compare,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> bool:
        left = self._evaluate_node(node.left, scope, depth=depth + 1)
        for operator_node, comparator_node in zip(
            node.ops, node.comparators, strict=True
        ):
            right = self._evaluate_node(comparator_node, scope, depth=depth + 1)
            if not _compare(left, operator_node, right):
                return False
            left = right
        return True

    def _subscript(
        self,
        node: ast.Subscript,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        value = self._evaluate_node(node.value, scope, depth=depth + 1)
        index = self._slice(node.slice, scope, depth=depth + 1)
        if type(value) is dict:
            _require_safe_hashable(index)
            try:
                return value[index]
            except (KeyError, TypeError) as exc:
                raise SafeExpressionError(
                    "Expression mapping key is unavailable"
                ) from exc
        if type(value) in {list, tuple, str} and type(index) in {int, slice}:
            if type(index) is slice:
                result_length = len(range(*index.indices(len(value))))
                if result_length > _result_length_limit(value):
                    raise SafeExpressionError("Expression result is too large")
            try:
                result = value[index]
            except (IndexError, ValueError) as exc:
                raise SafeExpressionError("Expression index is unavailable") from exc
            _check_result_size(result)
            return result
        raise SafeExpressionError("Subscripts require a built-in collection")

    def _slice(
        self,
        node: ast.expr,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        if isinstance(node, ast.Slice):
            lower = (
                self._evaluate_node(node.lower, scope, depth=depth + 1)
                if node.lower is not None
                else None
            )
            upper = (
                self._evaluate_node(node.upper, scope, depth=depth + 1)
                if node.upper is not None
                else None
            )
            step = (
                self._evaluate_node(node.step, scope, depth=depth + 1)
                if node.step is not None
                else None
            )
            if any(
                type(item) not in {type(None), int} for item in (lower, upper, step)
            ):
                raise SafeExpressionError("Slice bounds must be integers")
            if step == 0:
                raise SafeExpressionError("Slice step cannot be zero")
            return slice(lower, upper, step)
        return self._evaluate_node(node, scope, depth=depth + 1)

    def _mapping_attribute(
        self,
        node: ast.Attribute,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        if node.attr.startswith("_"):
            raise SafeExpressionError("Private attributes are not available")
        value = self._evaluate_node(node.value, scope, depth=depth + 1)
        if type(value) is not dict or node.attr not in value:
            raise SafeExpressionError("Attributes are limited to mapping keys")
        return value[node.attr]

    def _call(
        self,
        node: ast.Call,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Any:
        if not isinstance(node.func, ast.Name):
            raise SafeExpressionError("Method and attribute calls are not supported")
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise SafeExpressionError("Expanded call arguments are not supported")
        name = node.func.id
        args = [self._evaluate_node(arg, scope, depth=depth + 1) for arg in node.args]
        return self._call_function(name, args)

    def _call_function(self, name: str, args: list[Any]) -> Any:
        if name == "len" and len(args) == 1:
            return len(_safe_iterable(args[0]))
        if name in {"all", "any"} and len(args) == 1:
            values = _safe_iterable(args[0])
            if name == "all":
                return all(self._truth(value) for value in values)
            return any(self._truth(value) for value in values)
        if name in {"min", "max"} and args:
            values = list(_safe_iterable(args[0])) if len(args) == 1 else list(args)
            if not values:
                raise SafeExpressionError(f"{name}() requires at least one value")
            for value in values:
                _require_safe_value(value)
            return min(values) if name == "min" else max(values)
        if name == "sum" and len(args) in {1, 2}:
            values = _safe_iterable(args[0])
            start = args[1] if len(args) == 2 else 0
            _require_number(start)
            result: int | float = start
            for value in values:
                _require_number(value)
                result = _checked_number(result + value)
            return result
        if name == "abs" and len(args) == 1:
            _require_number(args[0])
            return _checked_number(abs(args[0]))
        if name == "isinstance" and len(args) == 2:
            types = args[1]
            if type(types) is tuple:
                if not types or any(not _is_safe_type(item) for item in types):
                    raise SafeExpressionError("isinstance() type is not permitted")
            elif not _is_safe_type(types):
                raise SafeExpressionError("isinstance() type is not permitted")
            return isinstance(args[0], types)
        if name in {"str", "int", "float"} and len(args) == 1:
            if type(args[0]) not in {type(None), bool, int, float, str}:
                raise SafeExpressionError(f"{name}() requires a scalar value")
            _check_result_size(args[0])
            result = _SAFE_TYPES[name](args[0])
            _check_result_size(result)
            return result
        if name == "bool" and len(args) == 1:
            return self._truth(args[0])
        if name in {"list", "tuple", "set"} and len(args) <= 1:
            values = [] if not args else list(_safe_iterable(args[0]))
            if name == "set":
                for value in values:
                    _require_safe_hashable(value)
            return _SAFE_TYPES[name](values)
        if name == "dict" and len(args) <= 1:
            if not args:
                return {}
            if type(args[0]) is dict:
                return dict(args[0])
            pairs = list(_safe_iterable(args[0]))
            if any(type(pair) not in {list, tuple} or len(pair) != 2 for pair in pairs):
                raise SafeExpressionError("dict() requires key/value pairs")
            for key, _ in pairs:
                _require_safe_hashable(key)
            return dict(pairs)
        raise SafeExpressionError(f"Function is not permitted: {name}")

    def _comprehension_values(
        self,
        node: ast.GeneratorExp | ast.ListComp | ast.SetComp,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> list[Any]:
        values: list[Any] = []
        for child_scope in self._comprehension_scopes(
            node.generators, scope, depth=depth + 1
        ):
            values.append(self._evaluate_node(node.elt, child_scope, depth=depth + 1))
            if len(values) > _MAX_COLLECTION_ITEMS:
                raise SafeExpressionError("Comprehension produced too many values")
        return values

    def _dictionary_comprehension(
        self,
        node: ast.DictComp,
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for child_scope in self._comprehension_scopes(
            node.generators, scope, depth=depth + 1
        ):
            key = self._evaluate_node(node.key, child_scope, depth=depth + 1)
            _require_safe_hashable(key)
            result[key] = self._evaluate_node(node.value, child_scope, depth=depth + 1)
            if len(result) > _MAX_COLLECTION_ITEMS:
                raise SafeExpressionError("Comprehension produced too many values")
        return result

    def _comprehension_scopes(
        self,
        generators: list[ast.comprehension],
        scope: dict[str, Any],
        *,
        depth: int,
    ) -> Iterable[dict[str, Any]]:
        def expand(
            index: int, active_scope: dict[str, Any]
        ) -> Iterable[dict[str, Any]]:
            self._tick(depth + index)
            if index >= len(generators):
                yield active_scope
                return
            generator = generators[index]
            if generator.is_async:
                raise SafeExpressionError("Async comprehensions are not supported")
            iterable = _safe_iterable(
                self._evaluate_node(
                    generator.iter,
                    active_scope,
                    depth=depth + index + 1,
                )
            )
            for item in iterable:
                self._tick(depth + index + 1)
                child_scope = dict(active_scope)
                self._assign_target(generator.target, item, child_scope)
                if all(
                    self._truth(
                        self._evaluate_node(
                            condition,
                            child_scope,
                            depth=depth + index + 1,
                        )
                    )
                    for condition in generator.ifs
                ):
                    yield from expand(index + 1, child_scope)

        return expand(0, scope)

    def _assign_target(
        self,
        target: ast.expr,
        value: Any,
        scope: dict[str, Any],
    ) -> None:
        if isinstance(target, ast.Name):
            scope[target.id] = value
            return
        if isinstance(target, ast.Tuple | ast.List):
            values = list(_safe_iterable(value))
            if len(values) != len(target.elts):
                raise SafeExpressionError("Comprehension unpacking length mismatch")
            for child_target, child_value in zip(target.elts, values, strict=True):
                self._assign_target(child_target, child_value, scope)
            return
        raise SafeExpressionError("Unsupported comprehension target")

    @staticmethod
    def _truth(value: Any) -> bool:
        if type(value) in {
            type(None),
            bool,
            int,
            float,
            str,
            list,
            tuple,
            dict,
            set,
            frozenset,
        }:
            return bool(value)
        raise SafeExpressionError("Expression truth value is not data-safe")


def _safe_iterable(value: Any) -> Any:
    if type(value) not in {str, list, tuple, dict, set, frozenset}:
        raise SafeExpressionError("Expression requires a built-in iterable")
    if len(value) > _MAX_COLLECTION_ITEMS:
        raise SafeExpressionError("Expression iterable is too large")
    return value


def _require_safe_hashable(
    value: Any,
    *,
    budget: list[int] | None = None,
) -> None:
    if budget is None:
        budget = [_MAX_EVALUATION_STEPS]
    _require_safe_hashable_at_depth(value, depth=0, budget=budget)


def _require_safe_hashable_at_depth(
    value: Any,
    *,
    depth: int,
    budget: list[int],
) -> None:
    budget[0] -= 1
    if budget[0] < 0:
        raise SafeExpressionError("Expression key exceeded its validation budget")
    if depth > _MAX_NESTING_DEPTH:
        raise SafeExpressionError("Expression key nesting is too deep")
    if type(value) not in {type(None), bool, int, float, str, tuple}:
        raise SafeExpressionError("Expression key is not data-safe")
    if type(value) is tuple:
        _safe_iterable(value)
        for item in value:
            _require_safe_hashable_at_depth(
                item,
                depth=depth + 1,
                budget=budget,
            )


def _is_safe_type(value: Any) -> bool:
    return any(value is allowed_type for allowed_type in _SAFE_TYPES.values())


def _require_safe_value(
    value: Any,
    *,
    depth: int = 0,
    budget: list[int] | None = None,
) -> None:
    if budget is None:
        budget = [_MAX_EVALUATION_STEPS]
    budget[0] -= 1
    if budget[0] < 0:
        raise SafeExpressionError("Expression value exceeded its validation budget")
    if depth > _MAX_NESTING_DEPTH:
        raise SafeExpressionError("Expression value nesting is too deep")
    if type(value) in {type(None), bool, int, float, str}:
        _check_result_size(value)
        return
    if type(value) in {list, tuple, set, frozenset}:
        _safe_iterable(value)
        for item in value:
            _require_safe_value(item, depth=depth + 1, budget=budget)
        return
    if type(value) is dict:
        _safe_iterable(value)
        for key, item in value.items():
            _require_safe_hashable(key, budget=budget)
            _require_safe_value(item, depth=depth + 1, budget=budget)
        return
    raise SafeExpressionError("Expression value is not data-safe")


def _require_number(value: Any) -> None:
    if type(value) not in {int, float}:
        raise SafeExpressionError("Expression requires numeric operands")
    _checked_number(value)


def _both_numbers(left: Any, right: Any) -> bool:
    return type(left) in {int, float} and type(right) in {int, float}


def _checked_number(value: Any) -> int | float:
    if type(value) is int:
        if value.bit_length() > _MAX_INTEGER_BITS:
            raise SafeExpressionError("Expression integer result is too large")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SafeExpressionError("Expression float result must be finite")
        return value
    raise SafeExpressionError("Expression requires numeric operands")


def _safe_multiply(left: Any, right: Any) -> Any:
    if _both_numbers(left, right):
        if type(left) is int and type(right) is int:
            if left.bit_length() + right.bit_length() > _MAX_INTEGER_BITS:
                raise SafeExpressionError("Expression integer result is too large")
        return _checked_number(operator.mul(left, right))

    sequence: Any
    multiplier: int
    if type(left) in {str, list, tuple} and type(right) is int:
        sequence, multiplier = left, right
    elif type(right) in {str, list, tuple} and type(left) is int:
        sequence, multiplier = right, left
    else:
        raise SafeExpressionError("Unsupported multiplication operands")
    if multiplier > 0 and len(sequence) * multiplier > _result_length_limit(sequence):
        raise SafeExpressionError("Expression result is too large")
    return sequence * multiplier


def _safe_add(left: Any, right: Any) -> Any:
    _check_result_size(left)
    _check_result_size(right)
    if len(left) + len(right) > _result_length_limit(left):
        raise SafeExpressionError("Expression result is too large")
    return operator.add(left, right)


def _compare(left: Any, operation: ast.cmpop, right: Any) -> bool:
    if isinstance(operation, ast.Is | ast.IsNot):
        result = left is right
        return not result if isinstance(operation, ast.IsNot) else result

    _require_safe_value(left)
    _require_safe_value(right)
    if isinstance(operation, ast.Eq):
        return left == right
    if isinstance(operation, ast.NotEq):
        return left != right
    if isinstance(operation, ast.Lt):
        return left < right
    if isinstance(operation, ast.LtE):
        return left <= right
    if isinstance(operation, ast.Gt):
        return left > right
    if isinstance(operation, ast.GtE):
        return left >= right
    if isinstance(operation, ast.In):
        return left in right
    if isinstance(operation, ast.NotIn):  # codespell:ignore
        return left not in right
    raise SafeExpressionError("Unsupported comparison operator")


def _check_result_size(value: Any) -> None:
    if type(value) is str and len(value) > _MAX_RESULT_SIZE:
        raise SafeExpressionError("Expression result is too large")
    if type(value) in {list, tuple, dict, set, frozenset}:
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise SafeExpressionError("Expression result is too large")
    if type(value) is int:
        _checked_number(value)
    if type(value) is float:
        _checked_number(value)


def _result_length_limit(value: Any) -> int:
    return _MAX_RESULT_SIZE if type(value) is str else _MAX_COLLECTION_ITEMS


def evaluate_expression(expression: str, context: dict[str, Any]) -> Any:
    """Evaluate a constrained expression against data-only context values."""
    return _Evaluator(context).evaluate(expression)


def evaluate_boolean_expression(
    expression: str,
    context: dict[str, Any],
) -> bool:
    """Evaluate a constrained expression and require a data-safe truth value."""
    evaluator = _Evaluator(context)
    return evaluator._truth(evaluator.evaluate(expression))


__all__ = [
    "SafeExpressionError",
    "evaluate_boolean_expression",
    "evaluate_expression",
]
