"""One-to-one comparison of stated planner requirements against bound actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning.ai_turn_schema import (
    AggregateRequirement,
    CompanionRequirement,
    FilterLogicRequirement,
    FilterRequirement,
    GoalRequirement,
    GroupingRequirement,
    HavingRequirement,
    IntervalRequirement,
    ModifyEditRequirement,
    NumericSlotRequirement,
    OptionRequirement,
    PlannedTurn,
    ProjectionRequirement,
    SearchTextRequirement,
    SortingRequirement,
    StatedRequirement,
    WindowRequirement,
)
from app.planning.plan_validator import PlanValidationError
from app.planning.turn_schema import (
    ModifyPreviousAction,
    QueryAction,
    TurnPlan,
    VerifyPreviousAction,
)


@dataclass(frozen=True)
class RequirementMatch:
    stated: StatedRequirement
    matched: bool


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "|".join(_norm(item) for item in value)
    return " ".join(str(value).casefold().split())


def extract_expressed(turn: TurnPlan) -> list[StatedRequirement]:
    expressed: list[StatedRequirement] = []
    for index, action in enumerate(turn.actions):
        if isinstance(action, QueryAction):
            expressed.extend(_from_query(index, action))
        elif isinstance(action, ModifyPreviousAction):
            expressed.extend(_from_modify(index, action))
        elif isinstance(action, VerifyPreviousAction):
            expressed.append(
                OptionRequirement(
                    action_index=index,
                    text="verify previous",
                    option="verify_previous",
                    value=True,
                )
            )
    return expressed


def _from_query(index: int, action: QueryAction) -> list[StatedRequirement]:
    items: list[StatedRequirement] = [
        GoalRequirement(action_index=index, text=f"goal {action.goal}", goal=action.goal)
    ]
    if action.filter_logic != "and":
        items.append(
            FilterLogicRequirement(
                action_index=index,
                text=f"filter logic {action.filter_logic}",
                filter_logic=action.filter_logic,
            )
        )
    for spec in action.filters:
        items.append(
            FilterRequirement(
                action_index=index,
                text=f"{spec.field} {spec.operator} {spec.value}",
                collection="filters",
                field=spec.field,
                operator=spec.operator,
                value=spec.value,
            )
        )
    for spec in action.denominator_filters:
        items.append(
            FilterRequirement(
                action_index=index,
                text=f"denominator {spec.field} {spec.operator} {spec.value}",
                collection="denominator_filters",
                field=spec.field,
                operator=spec.operator,
                value=spec.value,
            )
        )
    if action.search_text:
        items.append(
            SearchTextRequirement(
                action_index=index,
                text=action.search_text,
                search_text=action.search_text,
            )
        )
    if action.requested_fields:
        items.append(
            ProjectionRequirement(
                action_index=index,
                text=("project " + ", ".join(action.requested_fields))[:2000],
                requested_fields=list(action.requested_fields),
            )
        )
    for position, field in enumerate(action.group_by[:2]):
        part = action.group_value_part if position == 0 else action.secondary_group_value_part
        items.append(
            GroupingRequirement(
                action_index=index,
                text=f"group by {field}",
                field=field,
                position=0 if position == 0 else 1,
                value_part=part,
            )
        )
    if action.sort_by:
        items.append(
            SortingRequirement(
                action_index=index,
                text=f"sort {action.sort_by} {action.sort_direction or 'asc'}",
                field=action.sort_by,
                direction=action.sort_direction or "asc",
            )
        )
    if (
        action.interval_start
        or action.interval_end
        or action.interval_min_days is not None
        or action.interval_max_days is not None
    ):
        items.append(
            IntervalRequirement(
                action_index=index,
                text="interval",
                interval_start=action.interval_start,
                interval_end=action.interval_end,
                interval_min_days=action.interval_min_days,
                interval_max_days=action.interval_max_days,
            )
        )
    if action.aggregate is not None:
        items.append(
            AggregateRequirement(
                action_index=index,
                text=f"{action.aggregate.function} {action.aggregate.field or ''}".strip(),
                function=action.aggregate.function,
                field=action.aggregate.field,
                stats_value_part=action.stats_value_part,
            )
        )
    if action.companion_field:
        items.append(
            CompanionRequirement(
                action_index=index,
                text=action.companion_field,
                companion_field=action.companion_field,
            )
        )
    if action.having_min_count is not None:
        items.append(
            HavingRequirement(
                action_index=index,
                text=f"having {action.having_min_count}",
                having_min_count=action.having_min_count,
            )
        )
    for slot, value in (
        ("top_n", action.top_n),
        ("per_group_top_n", action.per_group_top_n),
        ("limit", action.limit),
        ("offset", action.offset),
    ):
        if value is not None:
            items.append(
                NumericSlotRequirement(
                    action_index=index,
                    text=f"{slot} {value}",
                    slot=slot,  # type: ignore[arg-type]
                    value=value,
                )
            )
    if action.window is not None:
        items.append(
            WindowRequirement(
                action_index=index,
                text="window",
                anchor=action.window.anchor,
                size=action.window.size,
                cursor=action.window.cursor,
            )
        )
    if action.include_missing:
        items.append(
            OptionRequirement(
                action_index=index, text="include missing", option="include_missing", value=True
            )
        )
    if action.sample:
        items.append(OptionRequirement(action_index=index, text="sample", option="sample", value=True))
    if action.exhaustive:
        items.append(
            OptionRequirement(action_index=index, text="exhaustive", option="exhaustive", value=True)
        )
    if action.presentation:
        items.append(
            OptionRequirement(
                action_index=index,
                text=f"presentation {action.presentation}",
                option="presentation",
                value=action.presentation,
            )
        )
    if action.verify_previous:
        items.append(
            OptionRequirement(
                action_index=index, text="verify previous", option="verify_previous", value=True
            )
        )
    for branch_index, branch in enumerate(action.compare):
        for spec in branch.filters:
            items.append(
                FilterRequirement(
                    action_index=index,
                    text=f"compare {branch.label or branch_index} {spec.field}",
                    collection="compare",
                    field=spec.field,
                    operator=spec.operator,
                    value=spec.value,
                    branch_index=branch_index,
                    branch_label=branch.label,
                )
            )
        if branch.search_text:
            items.append(
                SearchTextRequirement(
                    action_index=index,
                    text=branch.search_text,
                    search_text=branch.search_text,
                    branch_index=branch_index,
                    branch_label=branch.label,
                )
            )
    return items


def _from_modify(index: int, action: ModifyPreviousAction) -> list[StatedRequirement]:
    items: list[StatedRequirement] = []
    for spec in action.changes:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text=f"{spec.field} {spec.operator} {spec.value}",
                edit="filter",
                value=spec.model_dump(mode="json"),
            )
        )
    if action.goal:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"goal {action.goal}", edit="goal", value=action.goal)
        )
    if action.page:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"page {action.page}", edit="page", value=action.page)
        )
    if action.restore_frame:
        items.append(
            ModifyEditRequirement(
                action_index=index, text="restore frame", edit="restore_frame", value=action.restore_frame
            )
        )
    if action.sort_by:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"sort {action.sort_by}", edit="sort_by", value=action.sort_by)
        )
    if action.sort_direction:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text=f"sort {action.sort_direction}",
                edit="sort_direction",
                value=action.sort_direction,
            )
        )
    if action.limit is not None:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"limit {action.limit}", edit="limit", value=action.limit)
        )
    if action.offset is not None:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"offset {action.offset}", edit="offset", value=action.offset)
        )
    if action.sample is not None:
        items.append(
            ModifyEditRequirement(action_index=index, text=f"sample {action.sample}", edit="sample", value=action.sample)
        )
    if action.requested_fields is not None:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text="project " + ", ".join(action.requested_fields),
                edit="requested_fields",
                value=list(action.requested_fields),
            )
        )
    if action.window is not None:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text="window",
                edit="window",
                value=action.window.model_dump(mode="json"),
            )
        )
    if action.exhaustive is not None:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text=f"exhaustive {action.exhaustive}",
                edit="exhaustive",
                value=action.exhaustive,
            )
        )
    if action.presentation:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text=f"presentation {action.presentation}",
                edit="presentation",
                value=action.presentation,
            )
        )
    if action.group_value_part:
        items.append(
            ModifyEditRequirement(
                action_index=index,
                text=f"group value part {action.group_value_part}",
                edit="group_value_part",
                value=action.group_value_part,
            )
        )
    return items


def _same(stated: StatedRequirement, expressed: StatedRequirement) -> bool:
    if stated.kind != expressed.kind or stated.action_index != expressed.action_index:
        return False
    if isinstance(stated, GoalRequirement) and isinstance(expressed, GoalRequirement):
        return stated.goal == expressed.goal
    if isinstance(stated, FilterRequirement) and isinstance(expressed, FilterRequirement):
        return (
            stated.collection == expressed.collection
            and _norm(stated.field) == _norm(expressed.field)
            and stated.operator == expressed.operator
            and _norm(stated.value) == _norm(expressed.value)
            and stated.branch_index == expressed.branch_index
            and _norm(stated.branch_label or "") == _norm(expressed.branch_label or "")
        )
    if isinstance(stated, FilterLogicRequirement) and isinstance(expressed, FilterLogicRequirement):
        return stated.filter_logic == expressed.filter_logic
    if isinstance(stated, SearchTextRequirement) and isinstance(expressed, SearchTextRequirement):
        return (
            _norm(stated.search_text) == _norm(expressed.search_text)
            and stated.branch_index == expressed.branch_index
            and _norm(stated.branch_label or "") == _norm(expressed.branch_label or "")
        )
    if isinstance(stated, ProjectionRequirement) and isinstance(expressed, ProjectionRequirement):
        return [_norm(item) for item in stated.requested_fields] == [
            _norm(item) for item in expressed.requested_fields
        ]
    if isinstance(stated, GroupingRequirement) and isinstance(expressed, GroupingRequirement):
        return (
            _norm(stated.field) == _norm(expressed.field)
            and stated.position == expressed.position
            and stated.value_part == expressed.value_part
        )
    if isinstance(stated, SortingRequirement) and isinstance(expressed, SortingRequirement):
        return _norm(stated.field) == _norm(expressed.field) and stated.direction == expressed.direction
    if isinstance(stated, IntervalRequirement) and isinstance(expressed, IntervalRequirement):
        return (
            _norm(stated.interval_start) == _norm(expressed.interval_start)
            and _norm(stated.interval_end) == _norm(expressed.interval_end)
            and stated.interval_min_days == expressed.interval_min_days
            and stated.interval_max_days == expressed.interval_max_days
        )
    if isinstance(stated, AggregateRequirement) and isinstance(expressed, AggregateRequirement):
        return (
            _norm(stated.function) == _norm(expressed.function)
            and _norm(stated.field) == _norm(expressed.field)
            and stated.stats_value_part == expressed.stats_value_part
        )
    if isinstance(stated, CompanionRequirement) and isinstance(expressed, CompanionRequirement):
        return _norm(stated.companion_field) == _norm(expressed.companion_field)
    if isinstance(stated, HavingRequirement) and isinstance(expressed, HavingRequirement):
        return stated.having_min_count == expressed.having_min_count
    if isinstance(stated, NumericSlotRequirement) and isinstance(expressed, NumericSlotRequirement):
        return stated.slot == expressed.slot and stated.value == expressed.value
    if isinstance(stated, WindowRequirement) and isinstance(expressed, WindowRequirement):
        return stated.anchor == expressed.anchor and stated.size == expressed.size and stated.cursor == expressed.cursor
    if isinstance(stated, OptionRequirement) and isinstance(expressed, OptionRequirement):
        return stated.option == expressed.option and _norm(stated.value) == _norm(expressed.value)
    if isinstance(stated, ModifyEditRequirement) and isinstance(expressed, ModifyEditRequirement):
        return _norm(stated.edit) == _norm(expressed.edit) and _norm(stated.value) == _norm(expressed.value)
    return False


def _explode(requirements: list[StatedRequirement]) -> list[StatedRequirement]:
    """Split a multi-field projection into one requirement per field.

    A projection is a set of fields, not a sequence. Comparing the lists whole made
    parity order-sensitive, so a plan that projected exactly the requested fields in a
    different order was reported as having dropped them. Per-field entries make the
    comparison order-insensitive and strictly sharper: a genuinely missing field still
    fails to match, and the error names that field instead of the whole projection.
    """
    exploded: list[StatedRequirement] = []
    for item in requirements:
        if isinstance(item, ProjectionRequirement) and len(item.requested_fields) != 1:
            for name in item.requested_fields:
                exploded.append(
                    item.model_copy(update={"text": f"project {name}", "requested_fields": [name]})
                )
            continue
        exploded.append(item)
    return exploded


def check_requirement_parity(planned: PlannedTurn, bound: TurnPlan) -> None:
    expressed = _explode(extract_expressed(bound))
    unused = list(expressed)
    for stated in _explode(list(planned.stated_requirements)):
        match_index = next((index for index, item in enumerate(unused) if _same(stated, item)), None)
        if match_index is None:
            raise PlanValidationError(
                f"dropped_requirement: {stated.text}",
                code="dropped_requirement",
            )
        unused.pop(match_index)
