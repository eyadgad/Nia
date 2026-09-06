from __future__ import annotations

from app.execution.executor import ActionResult, ExecutionResult
from app.execution.row_projection import display_value, field_descriptors, semantic_value
from app.planning.catalog import FieldCatalog
from app.planning.plan_schema import FilterOperator, Predicate, QueryPlan


def _row_name(row: dict, catalog: FieldCatalog) -> str:
    """Prefer the canonical display name over the folded `canonical_name` column."""
    value = semantic_value(row, "student_name", catalog)
    text = "" if value is None else str(value).strip()
    return text or str(row.get("canonical_name") or "unnamed record")


def format_spoken_answer(
    plan: QueryPlan,
    result: ExecutionResult,
    catalog: FieldCatalog,
) -> str | None:
    """Terse spoken variant, or None when the written answer is already short."""
    if result.action_results:
        parts = [_spoken_action(item, plan, catalog) for item in result.action_results]
        spoken = " ".join(part for part in parts if part)
        return spoken or None
    if result.distinct_field:
        values = result.distinct_values
        plural = {"community": "communities", "school": "schools"}.get(
            result.distinct_field, f"{result.distinct_field} values"
        )
        singular = {"community": "community", "school": "school"}.get(
            result.distinct_field, result.distinct_field
        )
        if not values:
            return f"No {plural} recorded."
        noun = singular if len(values) == 1 else plural
        return f"{len(values)} {noun}: {_spoken_list(values)}."
    count_fact = next((fact for fact in result.facts if fact.name == "count"), None)
    if count_fact is not None:
        value = int(count_fact.value)
        noun = "student" if plan.scope.file_ids == (49,) else "record"
        return f"{value} {noun}." if value == 1 else f"{value} {noun}s."
    return None


def _spoken_action(action: ActionResult, plan: QueryPlan, catalog: FieldCatalog) -> str | None:
    file_ids = action.file_ids or plan.scope.file_ids
    if (
        action.value_counts
        and action.grouped_field
        and any(fact.name == "count" for fact in action.facts)
    ):
        recorded = sum(
            count for label, count in action.value_counts.items() if label != "Not recorded"
        )
        return f"{recorded} records have a recorded {action.grouped_field.replace('_', ' ')}."
    # A GROUP_BY that carries the values themselves was asked to show them. It also
    # publishes count_distinct so a caller can read the number, but that fact is not a
    # signal to replace the list with a tally -- COUNT_DISTINCT carries no values and
    # still falls through to the count below.
    if action.distinct_field and action.distinct_values:
        return _format_distinct(action.distinct_field, action.distinct_values, "authorized records")
    distinct_count = next((fact for fact in action.facts if fact.name == "count_distinct"), None)
    if distinct_count is not None:
        return _format_distinct_count(
            action.distinct_field or "value", int(distinct_count.value), "authorized records"
        )
    count_fact = next((fact for fact in action.facts if fact.name == "count"), None)
    if count_fact is not None:
        value = int(count_fact.value)
        noun = "student" if file_ids == (49,) else "record"
        return f"{value} {noun}." if value == 1 else f"{value} {noun}s."
    if action.rows:
        total = action.total_count
        names = [_row_name(row, catalog) for row in action.rows]
        preview = _spoken_list(names[:3])
        if action.sampled:
            noun = "students" if file_ids == (49,) else "records"
            return f"Here are {len(names)} random {noun}: {_spoken_list(names)}."
        if total is not None and (action.has_more or total > len(names)):
            noun = "student" if file_ids == (49,) else "record"
            plural = noun if total == 1 else f"{noun}s"
            more = " Say next to continue." if action.has_more or (total > (action.offset or 0) + len(names)) else ""
            return f"{total} {plural}. Starting with {preview}.{more}"
        if len(names) > 5:
            return f"{len(names)} records. Starting with {preview}."
        return _spoken_list(names) + "."
    return None


def _spoken_list(values: list[str]) -> str:
    items = [str(value) for value in values]
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def format_deterministic_answer(
    question: str,
    plan: QueryPlan,
    result: ExecutionResult,
    catalog: FieldCatalog,
) -> str:
    if result.action_results:
        verbose = len(result.action_results) == 1
        parts = [
            _format_action(action, plan, catalog, verbose=verbose)
            for action in result.action_results
        ]
        return " ".join(part for part in parts if part)

    labels = _scope_text(plan, catalog)
    if result.distinct_field:
        return _format_distinct(result.distinct_field, result.distinct_values, labels)
    if result.grouped_counts:
        return _format_grouped(result.grouped_counts, catalog)
    return "No matching authorized records were found."


def _format_action(
    action: ActionResult,
    plan: QueryPlan,
    catalog: FieldCatalog,
    *,
    verbose: bool,
) -> str:
    file_ids = action.file_ids or plan.scope.file_ids
    labels = _scope_text(plan, catalog, file_ids)
    constraint = _constraint_text(action.predicates)
    # Computed answers are rendered before any row page, so a calculation is never
    # reported as "showing 1-25 of N".
    if action.percentage is not None:
        return _format_percentage(action, labels, constraint)
    if action.stats is not None:
        return _format_stats(action, labels)
    if action.duplicates:
        return _format_duplicates(action, labels)
    if action.completeness:
        return _format_completeness(action, labels)
    if action.interval_summary is not None or action.intervals:
        return _format_intervals(action, labels)
    if action.ranked_groups and action.goal == "rank":
        return _format_ranked(action, labels)
    if (
        action.value_counts
        and action.grouped_field
        and any(fact.name == "count" for fact in action.facts)
    ):
        return _format_value_counts(action.grouped_field, action.value_counts, labels)
    # A GROUP_BY that carries the values themselves was asked to show them. It also
    # publishes count_distinct so a caller can read the number, but that fact is not a
    # signal to replace the list with a tally -- COUNT_DISTINCT carries no values and
    # still falls through to the count below.
    if action.distinct_field and action.distinct_values:
        return _format_distinct(action.distinct_field, action.distinct_values, labels)
    distinct_count = next((fact for fact in action.facts if fact.name == "count_distinct"), None)
    if distinct_count is not None:
        return _format_distinct_count(
            action.distinct_field or "value", int(distinct_count.value), labels
        )
    if action.distinct_field:
        return _format_distinct(action.distinct_field, action.distinct_values, labels)
    if action.grouped_counts:
        return _format_grouped(action.grouped_counts, catalog)
    compare_fact = next((fact for fact in action.facts if fact.name == "compare"), None)
    if compare_fact is not None:
        sides = compare_fact.value or []
        parts = []
        for side in sides:
            count = side.get("count")
            label = side.get("id") or "branch"
            if count is not None:
                parts.append(f"{label}: {count}")
        if parts:
            return "Comparison: " + "; ".join(parts) + "."
    aggregate = _format_numeric_aggregates(action, labels, constraint)
    if aggregate is not None:
        return aggregate
    if action.rows or (action.goal == "list" and action.total_count is not None):
        return _format_page(action, plan, catalog, labels, constraint, verbose=verbose)
    count_fact = next((fact for fact in action.facts if fact.name == "count"), None)
    if count_fact is not None:
        noun = "student" if file_ids == (49,) else "record"
        value = int(count_fact.value)
        if verbose:
            plural = noun if value == 1 else f"{noun}s"
            verb = "is" if value == 1 else "are"
            if constraint:
                return f"There {verb} {value} {plural} in the {labels} {constraint}."
            return f"There {verb} {value} {plural} in the {labels}."
        subject = _compact_subject(action.predicates, noun, plural=value != 1)
        return f"{subject}: {value} {noun}." if value == 1 else f"{subject}: {value} {noun}s."
    if action.evidence and action.evidence.items:
        shown = ", ".join(
            str(item.fields.get("student_name") or "unnamed record") for item in action.evidence.items
        )
        if verbose:
            return f"Matching records in the {labels}{(' ' + constraint) if constraint else ''}: {shown}."
        return f"{_compact_list_heading(action.predicates)} {shown}."
    return "No matching authorized records were found."


def _format_page(
    action: ActionResult,
    plan: QueryPlan,
    catalog: FieldCatalog,
    labels: str,
    constraint: str,
    *,
    verbose: bool,
) -> str:
    file_ids = action.file_ids or plan.scope.file_ids
    names = [_row_name(row, catalog) for row in action.rows]
    total = action.total_count
    if total is None:
        count_fact = next((fact for fact in action.facts if fact.name == "count"), None)
        if count_fact is not None:
            total = int(count_fact.value)
    total = int(total) if total is not None else len(names)
    offset = action.offset or 0
    page_size = action.page_size or len(names) or 25
    start = offset + 1 if names else 0
    end = offset + len(names)
    noun = "student" if file_ids == (49,) else "record"
    plural = noun if total == 1 else f"{noun}s"
    scope = f"in the {labels}{(' ' + constraint) if constraint else ''}"
    if total == 0 or not names:
        return f"There are no matching {plural} {scope}."
    header = f"There {'is' if total == 1 else 'are'} {total} {plural} {scope}."
    fields = list(action.projected_fields) or ["student_name"]
    descriptors = {
        item["name"]: item["label"]
        for item in field_descriptors(fields, file_ids, catalog)
    }
    lines: list[str] = []
    for index, row in enumerate(action.rows):
        name = _row_name(row, catalog)
        extras = [
            f"{descriptors[field]}: {display_value(semantic_value(row, field, catalog))}"
            for field in fields
            if field != "student_name"
        ]
        suffix = f" | {'; '.join(extras)}" if extras else ""
        lines.append(f"{offset + index + 1}. {name}{suffix}")
    numbered = "\n".join(lines)
    if action.sampled:
        return (
            f"Random sample of {len(names)} from {total} matching {plural} {scope}:\n"
            f"{numbered}"
        )
    if total <= len(names) and offset == 0 and not action.window_anchor:
        return f"{header}\n\n{numbered}"
    page = f"Showing {start}-{end} of {total}"
    if action.window_anchor and action.window_size:
        selected = action.window_count if action.window_count is not None else min(action.window_size, total)
        within_start = action.window_cursor + 1
        within_end = action.window_cursor + len(names)
        position = "last" if action.window_anchor == "end" else "first"
        page += f" (items {within_start}-{within_end} of the requested {position} {selected})"
    page += f":\n{numbered}"
    more = '\n\nSay "next" to continue.' if action.has_more else ""
    if verbose or action.has_more or total > page_size or action.window_anchor:
        return f"{header}\n{page}{more}"
    heading = _compact_list_heading(action.predicates)
    return f"{heading}\n{numbered}"


def _humanize(field: str | None) -> str:
    return (field or "value").replace("_", " ")


def _format_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "not available"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.{digits}f}"


_AGGREGATE_WORDS = {
    "min": "lowest",
    "max": "highest",
    "sum": "total",
    "avg": "average",
    "count_distinct": "distinct values",
}


def _format_numeric_aggregates(
    action: ActionResult,
    scope_text: str,
    constraint: str,
) -> str | None:
    """Render MIN / MAX / SUM / AVG results.

    Without this, a plan whose only output was a numeric aggregate fell through to
    "No matching authorized records were found" even though it had computed a value.
    """
    parts: list[str] = []
    for fact in action.facts:
        if fact.name not in _AGGREGATE_WORDS or fact.value is None:
            continue
        parts.append(f"{_AGGREGATE_WORDS[fact.name]} {_format_number(fact.value)}")
    if not parts:
        return None
    subject = f" {constraint}" if constraint else ""
    return f"In the {scope_text}{subject}: " + "; ".join(parts) + "."


def _format_ranked(action: ActionResult, scope_text: str) -> str:
    groups = action.ranked_groups
    primary, secondary = action.group_fields
    label = _humanize(primary)
    if not groups:
        return f"No {label} values are recorded in the {scope_text}."
    requested = action.requested_top_n
    shown = groups if requested is None else groups[:requested]
    lines = []
    for item in shown:
        name = item.label or "Not recorded"
        if secondary and item.secondary_label:
            name = f"{name} — {item.secondary_label}"
        lines.append(f"{name}: {item.count:,}")
    head = shown[0]
    total = sum(item.count for item in groups)
    if len(shown) == 1:
        return (
            f"{head.label or 'Not recorded'} has the most, with {head.count:,} "
            f"of {total:,} records in the {scope_text}."
        )
    heading = (
        f"Top {len(shown)} by {label}"
        if requested is not None and len(groups) > len(shown)
        else f"By {label}"
    )
    if secondary:
        heading += f" and {_humanize(secondary)}"
    suffix = (
        f" (showing {len(shown)} of {len(groups)} groups)"
        if len(groups) > len(shown)
        else ""
    )
    return f"{heading} in the {scope_text}{suffix}:\n" + "\n".join(lines)


def _format_stats(action: ActionResult, scope_text: str) -> str:
    stats = action.stats
    if stats is None or not stats.known_count:
        return (
            f"No numeric {_humanize(action.stats_field)} values are recorded "
            f"in the {scope_text}."
        )
    unit = "" if action.stats_value_part not in {"year", "decade"} else " (year)"
    parts = [
        f"lowest {_format_number(stats.minimum)}",
        f"highest {_format_number(stats.maximum)}",
        f"average {_format_number(stats.average)}",
        f"median {_format_number(stats.median)}",
    ]
    if stats.mode is not None:
        parts.append(f"most frequent {_format_number(stats.mode)} ({stats.mode_count} records)")
    return (
        f"{_humanize(action.stats_field).capitalize()}{unit} across "
        f"{stats.known_count:,} of {stats.record_count:,} records in the {scope_text}: "
        + "; ".join(parts)
        + "."
    )


def _format_percentage(action: ActionResult, scope_text: str, constraint: str) -> str:
    payload = action.percentage or {}
    numerator = int(payload.get("numerator") or 0)
    denominator = int(payload.get("denominator") or 0)
    percent = payload.get("percent")
    if not denominator:
        return f"There are no records to measure against in the {scope_text}."
    subject = f" {constraint}" if constraint else ""
    return (
        f"{percent:.2f}% ({numerator:,} of {denominator:,}) of the {scope_text}"
        f"{subject}."
    )


def _format_duplicates(action: ActionResult, scope_text: str) -> str:
    groups = action.duplicates
    field = _humanize(action.duplicate_field)
    if not groups:
        return f"No {field} value appears on more than one record in the {scope_text}."
    rows = sum(item.count for item in groups)
    extra = rows - len(groups)
    shared = sum(1 for item in groups if item.distinct_companions > 1)
    shared_note = (
        f" {shared} of them are shared by more than one distinct record."
        if shared
        else ""
    )
    lines = [
        f"{item.value}: {item.count}"
        + (f" ({', '.join(item.members)})" if item.members and item.count <= 6 else "")
        for item in groups
    ]
    return (
        f"{len(groups):,} {field} values appear on more than one record in the "
        f"{scope_text}, covering {rows:,} records ({extra:,} beyond the first in each "
        f"group).{shared_note}\n" + "\n".join(lines)
    )


def _format_completeness(action: ActionResult, scope_text: str) -> str:
    rows = action.completeness
    if not rows:
        return f"No records were available to measure in the {scope_text}."
    least = (action.completeness_direction or "desc").lower() == "asc"
    edge = rows[0].filled_fields
    tied = [item for item in rows if item.filled_fields == edge]
    names = "; ".join(f"{item.display_name} ({item.filled_fields}/{item.total_fields} fields)" for item in tied)
    wording = "least" if least else "most"
    return (
        f"Measured by how many catalog fields carry a value, the {wording} complete "
        f"records in the {scope_text}: {names}."
    )


def _format_intervals(action: ActionResult, scope_text: str) -> str:
    summary = action.interval_summary
    rows = action.intervals
    start, end = action.interval_fields or ("start", "end")
    span = f"{_humanize(start)} to {_humanize(end)}"
    if summary is None and not rows:
        return f"No record in the {scope_text} has both a {span} date."
    lines: list[str] = []
    if summary is not None and summary.record_count:
        lines.append(
            f"Across {summary.record_count:,} records in the {scope_text} with both dates, "
            f"{span} spans: shortest {_format_number(summary.minimum_days)} days, "
            f"longest {_format_number(summary.maximum_days)} days, average "
            f"{_format_number(summary.average_days)} days "
            f"({_format_number((summary.average_days or 0) / 365.25)} years), median "
            f"{_format_number(summary.median_days)} days."
        )
        if summary.impossible_count:
            lines.append(
                f"{summary.impossible_count} record(s) have an end date in an earlier year "
                f"than the start date, which is not possible."
            )
    for item in rows[:10]:
        note = " — impossible ordering" if item.is_impossible() else ""
        lines.append(
            f"{item.display_name}: {item.start_value} to {item.end_value} = "
            f"{_format_number(item.days)} days{note}"
        )
    return "\n".join(lines)


def _scope_text(
    plan: QueryPlan,
    catalog: FieldCatalog,
    file_ids: tuple[int, ...] | None = None,
) -> str:
    labels = [
        catalog.dataset(file_id).user_facing_label
        if catalog.dataset(file_id)
        else f"dataset {file_id}"
        for file_id in (file_ids or plan.scope.file_ids)
    ]
    return labels[0] if len(labels) == 1 else ", ".join(labels)


def _format_distinct(field: str, values: list[str], scope_text: str) -> str:
    singular = {"community": "community", "school": "school"}.get(field, field)
    plural = {"community": "communities", "school": "schools"}.get(field, f"{field} values")
    if not values:
        return f"No {plural} are recorded in the {scope_text}."
    noun = singular if len(values) == 1 else plural
    # Semicolons keep multi-word labels such as "Sault Ste. Marie, Michigan" readable
    # in a long enumeration.
    return f"The {scope_text} has {len(values)} {noun}: {'; '.join(values)}."


def _format_distinct_count(field: str, count: int, scope_text: str) -> str:
    singular = {"community": "community", "school": "school"}.get(field, field)
    plural = {"community": "communities", "school": "schools"}.get(
        field, f"{field.replace('_', ' ')} values"
    )
    noun = singular if count == 1 else plural
    return f"There {'is' if count == 1 else 'are'} {count} {noun} in the {scope_text}."


def _format_value_counts(field: str, counts: dict[str, int], scope_text: str) -> str:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    total = sum(count for _label, count in ordered)
    missing = sum(count for label, count in ordered if label == "Not recorded")
    recorded = total - missing
    visible = [(label, count) for label, count in ordered if label != "Not recorded"]
    shown = visible[:10]
    details = "; ".join(f"{label}: {count}" for label, count in shown)
    remainder = len(visible) - len(shown)
    if remainder:
        details += f"; plus {remainder} other recorded values"
    label = field.replace("_", " ").capitalize()
    missing_text = f"; {missing} not recorded" if missing else ""
    return (
        f"{label} summary for the {scope_text}: {total} records; "
        f"{recorded} with a recorded value{missing_text}. Most frequent: {details}."
    )


def _format_grouped(grouped: dict[int, int], catalog: FieldCatalog) -> str:
    parts = [
        f"{catalog.dataset(file_id).user_facing_label if catalog.dataset(file_id) else file_id}: {count}"
        for file_id, count in grouped.items()
    ]
    return "Current authorized record counts: " + "; ".join(parts) + "."


def _compact_subject(predicates: list[Predicate], noun: str, *, plural: bool) -> str:
    community = _community(predicates)
    if community:
        return community
    prefix = _starts_with(predicates)
    if prefix:
        return f"Names starting with {prefix}"
    return noun.capitalize() + ("s" if plural else "")


def _compact_list_heading(predicates: list[Predicate]) -> str:
    prefix = _starts_with(predicates)
    if prefix:
        return f"Students whose names start with {prefix}:"
    community = _community(predicates)
    if community:
        return f"Students from {community}:"
    return "Matching records:"


def _community(predicates: list[Predicate]) -> str | None:
    for predicate in predicates:
        if predicate.operator is FilterOperator.EQUALS and predicate.field == "community":
            return str(predicate.value)
    return None


def _starts_with(predicates: list[Predicate]) -> str | None:
    for predicate in predicates:
        if predicate.operator is FilterOperator.STARTS_WITH:
            return str(predicate.value)
    return None


def format_access_denied() -> str:
    return "That request is outside the datasets available in this session."


def format_unplanned(detail: str) -> str:
    return (
        "I wasn't able to answer that one accurately. "
        "Could you try asking it a different way?"
    )


def _constraint_text(predicates: list[Predicate]) -> str:
    parts: list[str] = []
    for predicate in predicates:
        if predicate.operator is FilterOperator.STARTS_WITH:
            parts.append(f"whose names start with {predicate.value}")
        elif predicate.operator is FilterOperator.EQUALS and predicate.field == "community":
            parts.append(f"from {predicate.value}")
        elif predicate.operator is FilterOperator.IS_TRUE and predicate.field == "deceased_status":
            parts.append("recorded as deceased")
        elif predicate.operator is FilterOperator.YEAR_EQUALS:
            parts.append(f"with {predicate.field.replace('_', ' ')} in {predicate.value}")
        elif predicate.operator is FilterOperator.BEFORE:
            parts.append(f"with {predicate.field.replace('_', ' ')} before {predicate.value}")
        elif predicate.operator is FilterOperator.AFTER:
            parts.append(f"with {predicate.field.replace('_', ' ')} after {predicate.value}")
    return " ".join(parts)
