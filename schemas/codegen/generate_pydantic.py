"""Generate Pydantic v2 models from the canonical JSON Schemas in schemas/."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
OUTPUT_DIR = REPO_ROOT / "packages" / "core" / "src" / "skiljo_core" / "schemas"


def write_schema_exports() -> None:
    (OUTPUT_DIR / "__init__.py").write_text(
        "from .rule_schema import Citation, Rule, Span\n\n"
        '__all__ = ["Citation", "Rule", "Span"]\n'
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # datamodel-codegen recursively parses every file under --input, so point it at a
    # directory containing only the *.schema.json files — schemas/codegen/ itself (this
    # script, generate_zod.ts) is not valid JSON/YAML and would otherwise hard-fail.
    with tempfile.TemporaryDirectory() as tmp_dir:
        for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
            shutil.copy2(schema_file, tmp_dir)
        result = subprocess.run(
            [
                "datamodel-codegen",
                "--input", tmp_dir,
                "--input-file-type", "jsonschema",
                "--output", str(OUTPUT_DIR),
                "--output-model-type", "pydantic_v2.BaseModel",
            ],
            check=False,
        )
    if result.returncode == 0:
        write_schema_exports()
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
