"""Recovering from a misspelt name instead of answering "no matching records".

A researcher reading a handwritten register types what they see, and what they see is often
a letter or two off the form the record was indexed under. Answering "no matching records"
is then both wrong and unhelpful: the person is there, and the researcher cannot tell
whether they mistyped or the record genuinely is not held.

How close the guess was decides what to do with it, which is the distinction a person would
draw themselves:

* exactly one person, one edit away -- a typo. Answer the question about that person and say
  which name was read, so the correction is visible rather than silent.
* anything less certain -- two or three edits, or several people equally close -- ask. The
  researcher knows which one they meant and NIA does not.

Nothing here interprets language. It compares the name that was searched for against the
names the records actually carry, which is arithmetic over the index the backfill built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning.catalog import FieldCatalog
from app.planning.plan_schema import FilterOperator, Predicate, QueryPlan

# Paths whose values are a person's name in some recorded form. A filter on any of them is
# a filter on who the record is about, which is what can be misspelt.
_NAME_PATHS = ("names", "canonical.display_name", "canonical.name_parts.")


@dataclass(frozen=True)
class NameSuggestion:
    display_name: str
    file_id: int
    source_row_id: int
    distance: int


@dataclass(frozen=True)
class NameCorrection:
    """What to do about a name that matched nothing."""

    searched_for: str
    suggestions: tuple[NameSuggestion, ...]

    @property
    def certain(self) -> NameSuggestion | None:
        """The single person one edit away, if that is unambiguous."""
        closest = [item for item in self.suggestions if item.distance == 1]
        if len(closest) == 1 and len(self.suggestions) == 1:
            return closest[0]
        return None


def is_name_field(field_name: str, file_ids: tuple[int, ...], catalog: FieldCatalog) -> bool:
    for file_id in file_ids:
        spec = catalog.resolve_field(file_id, field_name)
        if spec is None:
            continue
        path = spec.canonical_json_path or ""
        if path in _NAME_PATHS[:2] or path.startswith(_NAME_PATHS[2]):
            return True
    return False


def searched_name(plan: QueryPlan, catalog: FieldCatalog) -> str:
    """The name the plan looked for, reassembled from its filters.

    A multi-word name reaches the plan as one filter per token -- that is how a token index
    is matched -- so the words are joined back in plan order to recover what was typed.
    """
    words: list[str] = []
    for step in plan.steps:
        file_ids = step.file_ids or plan.scope.file_ids
        for predicate in step.where:
            for leaf in predicate.leaves():
                if not leaf.field or leaf.operator in {
                    FilterOperator.IS_KNOWN,
                    FilterOperator.IS_UNKNOWN,
                }:
                    continue
                if not is_name_field(leaf.field, file_ids, catalog):
                    continue
                for item in leaf.value if isinstance(leaf.value, list) else [leaf.value]:
                    text = str(item or "").strip()
                    if text and text not in words:
                        words.append(text)
    return " ".join(words)


def rewrite_for(plan: QueryPlan, catalog: FieldCatalog, corrected: str) -> QueryPlan:
    """The same plan, asking about the corrected name instead.

    Every name filter is replaced by one CONTAINS per token of the corrected name, on the
    field the planner chose. The rest of the plan -- its goal, grouping, projection, limits
    -- is untouched, so the researcher gets the answer to the question they asked.
    """
    tokens = [token for token in corrected.split() if token]
    if not tokens:
        return plan
    steps = []
    for step in plan.steps:
        file_ids = step.file_ids or plan.scope.file_ids
        kept: list[Predicate] = []
        replaced = False
        for predicate in step.where:
            leaves = predicate.leaves()
            if any(
                leaf.field and is_name_field(leaf.field, file_ids, catalog) for leaf in leaves
            ):
                if not replaced:
                    field_name = next(
                        leaf.field
                        for leaf in leaves
                        if leaf.field and is_name_field(leaf.field, file_ids, catalog)
                    )
                    kept.extend(
                        Predicate(
                            field=field_name,
                            operator=FilterOperator.CONTAINS,
                            value=token,
                        )
                        for token in tokens
                    )
                    replaced = True
                continue
            kept.append(predicate)
        steps.append(step.model_copy(update={"where": kept}) if replaced else step)
    return plan.model_copy(update={"steps": steps})


def from_rows(searched_for: str, rows: list[dict[str, Any]]) -> NameCorrection | None:
    """Build a correction from the gateway's suggestions, dropping exact matches.

    A zero-distance row cannot be why the search failed, so it is not a suggestion.
    """
    suggestions = tuple(
        NameSuggestion(
            display_name=str(row.get("display_name") or "").strip(),
            file_id=int(row.get("file_id") or 0),
            source_row_id=int(row.get("source_row_id") or 0),
            distance=int(row.get("distance") or 0),
        )
        for row in rows
        if int(row.get("distance") or 0) > 0 and str(row.get("display_name") or "").strip()
    )
    if not suggestions:
        return None
    return NameCorrection(searched_for=searched_for, suggestions=suggestions)


def ask_text(correction: NameCorrection) -> str:
    """The question to put back to the researcher when the guess is not certain."""
    names = [item.display_name for item in correction.suggestions]
    if len(names) == 1:
        return (
            f'No record matches "{correction.searched_for}". '
            f"Did you mean {names[0]}?"
        )
    listed = "; ".join(names)
    return (
        f'No record matches "{correction.searched_for}". '
        f"Did you mean one of these: {listed}?"
    )


def corrected_prefix(searched_for: str, corrected: str) -> str:
    """Said before the answer, so the correction is never silent."""
    return f'No record matches "{searched_for}". Showing {corrected} instead.'
