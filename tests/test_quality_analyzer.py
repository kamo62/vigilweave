from app.services.quality_analyzer import analyze_files


def test_python_complexity_uses_parser_not_keyword_strings(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plain.py").write_text(
        ("def plain():\n    text = 'if for while and or'\n    return text\n"),
        encoding="utf-8",
    )
    (repo / "branchy.py").write_text(
        ("def branchy(value):\n    if value > 0:\n        return value\n    return 0\n"),
        encoding="utf-8",
    )

    metrics, _ = analyze_files(repo, scan_id=1)
    by_file = {item.file_path: item for item in metrics}

    assert by_file["plain.py"].cyclomatic_complexity == 1
    assert by_file["branchy.py"].cyclomatic_complexity >= 2
