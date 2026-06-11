import json
import subprocess
from pathlib import Path
import jsonschema

SCHEMA = json.loads((Path("rune/review/schema.json")).read_text())


def test_review_json_matches_schema(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\nNever use TS.\n")
    result = subprocess.run(
        ["rune", "review", "--json"], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    jsonschema.validate(instance=data, schema=SCHEMA)
    assert data["schema_version"] == "1.0"
