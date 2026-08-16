from skiljo_core.db.models import Base, TicketRecord


def test_all_tables_registered() -> None:
    expected = {
        "policies",
        "ticket_batches",
        "ticket_records",
        "skills",
        "skill_versions",
        "simulation_runs",
        "simulation_results",
        "llm_calls",
        "llm_cache",
        "jobs",
        "eval_runs",
    }
    assert set(Base.metadata.tables.keys()) == expected


def test_ticket_records_define_batch_position_index() -> None:
    table = TicketRecord.__table__

    assert "position" in table.columns
    assert any(
        tuple(column.name for column in index.columns) == ("batch_id", "position")
        for index in table.indexes
    )
