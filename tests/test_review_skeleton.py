import subprocess


def test_review_skeleton_exits_zero():
    result = subprocess.run(["rune", "review", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "review" in result.stdout.lower()
