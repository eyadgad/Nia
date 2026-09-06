"""Catalog-aware repairs for AI plans. No free-text parsing."""

from __future__ import annotations

from typing import Any

from app.planning.ai_turn_schema import (
    FilterRequirement,
    GroupingRequirement,
    PlannedQueryAction,
    PlannedTurn,
    SortingRequirement,
)
from app.planning.catalog import FieldCatalog, FieldSpec
from app.planning.turn_schema import FilterSpec
from app.planning.value_expansion import exact_category_terms

_TRUE_TOKENS = frozenset({"deceased", "yes", "true", "y", "t", "1"})
_FALSE_TOKENS = frozenset({"no", "false", "n", "f", "0"})
_GENDER_IN = {
    "female": ["F", "female", "f", "woman", "girl"],
    "f": ["F", "female", "f"],
    "male": ["M", "male", "m", "man", "boy"],
    "m": ["M", "male", "m"],
    "woman": ["F", "female", "f", "woman"],
    "man": ["M", "male", "m", "man"],
}


def coerce_planned_turn(
    planned: PlannedTurn,
    catalog: FieldCatalog,
    file_id: int,
) -> PlannedTurn:
    """Rewrite catalog-illegal slots so parity and validation stay aligned."""
    actions = []
    changed = False
    for action in planned.actions:
        if isinstance(action, PlannedQueryAction):
            rewritten = _coerce_query(action, catalog, file_id)
            changed = changed or rewritten != action
            actions.append(rewritten)
        else:
            actions.append(action)
    if not changed:
        return planned
    requirements = [
        _coerce_requirement(item, catalog, file_id) for item in planned.stated_requirements
    ]
    return planned.model_copy(update={"actions": actions, "stated_requirements": requirements})


def _coerce_query(
    action: PlannedQueryAction,
    catalog: FieldCatalog,
    file_id: int,
) -> PlannedQueryAction:
    updates: dict[str, Any] = {}
    filters: list[FilterSpec] = []
    for item in action.filters:
        filters.extend(_coerce_filters(item, catalog, file_id))
    if filters != list(action.filters):
        updates["filters"] = filters
    group_by = [
        _remap_missing_field(name, action, catalog, file_id) or name for name in action.group_by
    ]
    if group_by != list(action.group_by):
        updates["group_by"] = group_by
    if action.sort_by:
        remapped = _remap_missing_field(action.sort_by, action, catalog, file_id)
        if remapped and remapped != action.sort_by:
            updates["sort_by"] = remapped
        elif (
            action.goal == "list"
            and action.sort_by in {"first_name", "last_name", "middle_names"}
            and action.requested_fields
            and action.sort_by not in action.requested_fields
            and catalog.resolve_field(file_id, "student_name") is not None
        ):
            updates["sort_by"] = "student_name"
    elif action.goal == "list" and action.window is not None:
        if catalog.resolve_field(file_id, "student_name") is not None:
            updates["sort_by"] = "student_name"
            updates["sort_direction"] = action.sort_direction or "asc"
    if action.aggregate is not None and action.aggregate.field:
        remapped = _remap_missing_field(action.aggregate.field, action, catalog, file_id)
        if remapped and remapped != action.aggregate.field:
            updates["aggregate"] = action.aggregate.model_copy(update={"field": remapped})
    return action.model_copy(update=updates) if updates else action


def _coerce_filter(spec: FilterSpec, catalog: FieldCatalog, file_id: int) -> FilterSpec:
    field_name = _remap_missing_field(spec.field, None, catalog, file_id) or spec.field
    field = catalog.resolve_field(file_id, field_name)
    updates: dict[str, Any] = {}
    if field_name != spec.field:
        updates["field"] = field_name
        field = catalog.resolve_field(file_id, field_name)
    if field is not None and (field.semantic_type or "").lower() == "boolean":
        token = _token(spec.value)
        if spec.operator in {"EQUALS", "CONTAINS", "CONTAINS_ANY", "IN"} and token:
            if token in _TRUE_TOKENS:
                return spec.model_copy(
                    update={**updates, "operator": "IS_TRUE", "value": None}
                )
            if token in _FALSE_TOKENS:
                return spec.model_copy(
                    update={**updates, "operator": "IS_FALSE", "value": None}
                )
    exact = _exact_category_match(field, spec)
    if exact is not None:
        return spec.model_copy(update={**updates, **exact})
    if field is not None and field.semantic_field == "gender":
        widened = _gender_values(spec.value)
        if widened is not None:
            updates["operator"] = "IN"
            updates["value"] = widened
    return spec.model_copy(update=updates) if updates else spec


def _coerce_filters(spec: FilterSpec, catalog: FieldCatalog, file_id: int) -> list[FilterSpec]:
    """One planned filter, as the one or more filters it should compile to.

    Only a token index splits, and sibling filters are ANDed, which is the semantics a
    multi-word name needs: every token must be present.
    """
    field_name = _remap_missing_field(spec.field, None, catalog, file_id) or spec.field
    field = catalog.resolve_field(file_id, field_name)
    tokens = _token_index_tokens(field, spec)
    if tokens is not None:
        return [
            FilterSpec(field=field_name, operator="CONTAINS", value=token) for token in tokens
        ]
    return [_coerce_filter(spec, catalog, file_id)]


def _token_index_tokens(field: FieldSpec | None, spec: FilterSpec) -> list[str] | None:
    """Match a bag of tokens token by token, never as a phrase.

    A field flagged token_index stores one token per recorded form and renders as a joined
    list -- name_search reads "albert, penance, pinnance". Searching that for the phrase
    "Albert Penance" cannot match, so a record that is plainly in the list came back as no
    record at all.

    The words of a name are all required, so this asks for every token. CONTAINS_ANY would
    be an OR and would return every Albert on the list.
    """
    if field is None or spec.operator not in {"CONTAINS", "EQUALS", "CONTAINS_ANY"}:
        return None
    if not (field.validation_rules or {}).get("token_index"):
        return None
    raw = spec.value if isinstance(spec.value, list) else [spec.value]
    tokens: list[str] = []
    for item in raw:
        tokens.extend(part for part in str(item or "").split() if part)
    if len(tokens) < 2:
        return None
    return tokens


def _exact_category_match(field: FieldSpec | None, spec: FilterSpec) -> dict[str, Any] | None:
    """Match an enumerated field by equality where a substring search would be wrong.

    A field that publishes recorded_values holds a closed set of categories, and asking for
    one of them with CONTAINS is a category match written as a text search. Whether that is
    safe depends on the categories -- exact_category_terms decides, and its docstring gives
    both failure modes.

    Only rewrites the operator; the field and value the planner chose are its own.
    """
    if field is None or spec.operator not in {"CONTAINS", "CONTAINS_ANY"}:
        return None
    requested = spec.value if isinstance(spec.value, list) else [spec.value]
    matched = exact_category_terms(
        (field.validation_rules or {}).get("recorded_values"), requested
    )
    if not matched:
        return None
    if len(matched) == 1:
        return {"operator": "EQUALS", "value": matched[0]}
    return {"operator": "IN", "value": matched}


def _coerce_requirement(item: Any, catalog: FieldCatalog, file_id: int) -> Any:
    if isinstance(item, FilterRequirement):
        spec = FilterSpec(field=item.field, operator=item.operator, value=item.value)
        rewritten = _coerce_filter(spec, catalog, file_id)
        if rewritten != spec:
            return item.model_copy(
                update={
                    "field": rewritten.field,
                    "operator": rewritten.operator,
                    "value": rewritten.value,
                }
            )
    if isinstance(item, GroupingRequirement):
        remapped = _remap_missing_field(item.field, None, catalog, file_id)
        if remapped and remapped != item.field:
            return item.model_copy(update={"field": remapped})
    if isinstance(item, SortingRequirement):
        remapped = _remap_missing_field(item.field, None, catalog, file_id)
        if remapped and remapped != item.field:
            return item.model_copy(update={"field": remapped})
        if item.field in {"first_name", "last_name", "middle_names"}:
            if catalog.resolve_field(file_id, "student_name") is not None:
                return item.model_copy(update={"field": "student_name"})
    return item


def _remap_missing_field(
    name: str,
    action: PlannedQueryAction | None,
    catalog: FieldCatalog,
    file_id: int,
) -> str | None:
    if catalog.resolve_field(file_id, name) is not None:
        return None
    if name.strip().casefold() != "count":
        return None
    candidates: list[str] = []
    if action is not None:
        candidates.extend(action.requested_fields)
        if action.companion_field:
            candidates.append(action.companion_field)
        candidates.extend(item for item in action.group_by if item != name)
        if action.sort_by and action.sort_by != name:
            candidates.append(action.sort_by)
    unique = []
    for item in candidates:
        if catalog.resolve_field(file_id, item) is None:
            continue
        if item not in unique:
            unique.append(item)
    return unique[0] if len(unique) == 1 else None


def _token(value: Any) -> str:
    if isinstance(value, list):
        if len(value) != 1:
            return ""
        value = value[0]
    return str(value or "").strip().casefold()


def _gender_values(value: Any) -> list[str] | None:
    tokens = value if isinstance(value, list) else [value]
    widened: list[str] = []
    matched = False
    for item in tokens:
        family = _GENDER_IN.get(str(item or "").strip().casefold())
        if family is None:
            if item not in (None, ""):
                widened.append(str(item))
            continue
        matched = True
        for term in family:
            if term not in widened:
                widened.append(term)
    return widened if matched else None


def spec_is_boolean(spec: FieldSpec | None) -> bool:
    return spec is not None and (spec.semantic_type or "").lower() == "boolean"
