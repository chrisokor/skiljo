from skiljo_core.db.models import Base


def test_all_tables_registered() -> None:
    expected = {
        "policies",
        "skills",
        "skill_versions",
        "simulation_runs",
        "simulation_results",
        "llm_calls",
        "jobs",
        "eval_runs",
    }
    assert set(Base.metadata.tables.keys()) == expected
