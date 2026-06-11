import subprocess
import sys


def test_l1_no_heavy_imports(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\n")
    code = (
        "import sys, json; "
        "from rune.review.cli import review_app; "
        "from typer.testing import CliRunner; "
        "runner = CliRunner(); "
        f"runner.invoke(review_app, ['--json', '{tmp_path}']); "
        "loaded = set(sys.modules.keys()); "
        "heavy = [m for m in ('textual','torch','transformers','sentence_transformers') if m in loaded]; "
        "print(json.dumps(heavy))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    heavy = result.stdout.strip().splitlines()[-1]
    assert heavy == "[]", f"L1 path imported heavy modules: {heavy}"
