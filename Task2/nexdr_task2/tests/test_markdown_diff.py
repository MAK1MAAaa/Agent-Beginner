from nexdr.utils.markdown_diff import build_unified_diff
from nexdr.utils.markdown_diff import summarize_markdown_changes


def test_unified_diff_and_summary():
    original = "# Title\n\nA\n\nB\n"
    edited = "# Title\n\nA updated\n\nB\n\nC\n"

    diff = build_unified_diff(original, edited)
    summary = summarize_markdown_changes(original, edited)

    assert "--- markdown_report.original.md" in diff
    assert "+++ markdown_report.user_edited.md" in diff
    assert summary["added_lines"] >= 1
    assert summary["modified_paragraphs"] >= 1
