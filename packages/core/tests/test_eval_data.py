from pathlib import Path

import yaml

from skiljo_core.schemas.skill_schema import Skill

EVAL_TRAIN_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "train"


def test_all_eval_examples_have_schema_valid_ground_truth() -> None:
    skill_files = sorted(EVAL_TRAIN_DIR.glob("*.skill.yaml"))
    assert len(skill_files) == 20, f"expected 20 examples, found {len(skill_files)}"

    for skill_file in skill_files:
        policy_file = skill_file.with_name(skill_file.name.replace(".skill.yaml", ".policy.txt"))
        assert policy_file.exists(), f"missing policy text for {skill_file.name}"
        assert policy_file.stat().st_size > 0, f"empty policy text for {skill_file.name}"

        with open(skill_file) as f:
            raw = yaml.safe_load(f)
        skill = Skill.model_validate(raw)
        assert skill.skill_name
