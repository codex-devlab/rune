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


def test_no_torch_without_l2(tmp_path):
    import sys, subprocess
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\n")
    code = (
        "import sys; "
        "from rune.review.cli import review_app; "
        "from typer.testing import CliRunner; "
        f"CliRunner().invoke(review_app, ['--json', '{tmp_path}']); "
        "loaded = set(sys.modules.keys()); "
        "heavy = [m for m in ('torch','transformers') if m in loaded]; "
        "print('|'.join(heavy))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    assert last == "", f"--json path loaded heavy: {last}"
