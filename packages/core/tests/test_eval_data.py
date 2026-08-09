from pathlib import Path

import pytest
import yaml

from skiljo_core.schemas.skill_schema import Skill

EVAL_DIR = Path(__file__).resolve().parents[3] / "data" / "eval"
EVAL_TRAIN_DIR = EVAL_DIR / "train"
EVAL_DEV_DIR = EVAL_DIR / "dev"
EVAL_TEST_DIR = EVAL_DIR / "test"

# plan #51: dataset expanded to 60 labeled examples, split 30/15/15.
EXPECTED_SPLIT_SIZES = {
    "train": 30,
    "dev": 15,
    "test": 15,
}


def _validate_split(split_dir: Path, expected_count: int) -> None:
    skill_files = sorted(split_dir.glob("*.skill.yaml"))
    assert len(skill_files) == expected_count, (
        f"expected {expected_count} examples in {split_dir}, found {len(skill_files)}"
    )

    for skill_file in skill_files:
        policy_file = skill_file.with_name(skill_file.name.replace(".skill.yaml", ".policy.txt"))
        assert policy_file.exists(), f"missing policy text for {skill_file.name}"
        assert policy_file.stat().st_size > 0, f"empty policy text for {skill_file.name}"

        with open(skill_file) as f:
            raw = yaml.safe_load(f)
        skill = Skill.model_validate(raw)
        assert skill.skill_name


def test_all_train_examples_have_schema_valid_ground_truth() -> None:
    _validate_split(EVAL_TRAIN_DIR, EXPECTED_SPLIT_SIZES["train"])


def test_all_dev_examples_have_schema_valid_ground_truth() -> None:
    _validate_split(EVAL_DEV_DIR, EXPECTED_SPLIT_SIZES["dev"])


@pytest.mark.skip(
    reason="data/eval/test/ is held-out; validated in CI only, never inspected locally "
    "(CLAUDE.md system invariant 5). See data/eval/test/.CODEOWNERS."
)
def test_all_test_examples_have_schema_valid_ground_truth() -> None:
    _validate_split(EVAL_TEST_DIR, EXPECTED_SPLIT_SIZES["test"])


def test_dataset_totals_60_examples_across_splits() -> None:
    total = sum(
        len(list((EVAL_DIR / split).glob("*.skill.yaml"))) for split in EXPECTED_SPLIT_SIZES
    )
    assert total == 60, f"expected 60 total labeled examples, found {total}"
