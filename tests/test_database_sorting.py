from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_structured_list_migration_uses_validated_sort_field_and_stable_tiebreaker():
    sql = (
        ROOT / "backend" / "app" / "db" / "migrations" / "017_structured_sort.sql"
    ).read_text(encoding="utf-8")

    assert "registry.semantic_field = p_sort_field" in sql
    assert "WHEN registry.sortable" in sql
    assert "matched.sort_value" in sql
    assert "matched.source_row_id ASC" in sql
    assert "ORDER BY\n        CASE WHEN upper" not in sql
