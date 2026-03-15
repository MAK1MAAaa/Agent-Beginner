# Copyright (c) Nex-AGI. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import difflib
import re


def build_unified_diff(
    original_text: str,
    edited_text: str,
    from_name: str = "markdown_report.original.md",
    to_name: str = "markdown_report.user_edited.md",
) -> str:
    diff_lines = difflib.unified_diff(
        original_text.splitlines(),
        edited_text.splitlines(),
        fromfile=from_name,
        tofile=to_name,
        lineterm="",
    )
    return "\n".join(diff_lines)


def summarize_markdown_changes(original_text: str, edited_text: str) -> dict:
    original_lines = original_text.splitlines()
    edited_lines = edited_text.splitlines()
    matcher = difflib.SequenceMatcher(None, original_lines, edited_lines)

    added_lines = 0
    removed_lines = 0
    modified_blocks = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added_lines += j2 - j1
        elif tag == "delete":
            removed_lines += i2 - i1
        elif tag == "replace":
            modified_blocks += 1
            removed_lines += i2 - i1
            added_lines += j2 - j1

    original_paragraphs = _split_paragraphs(original_text)
    edited_paragraphs = _split_paragraphs(edited_text)
    paragraph_matcher = difflib.SequenceMatcher(None, original_paragraphs, edited_paragraphs)

    added_paragraphs = 0
    removed_paragraphs = 0
    modified_paragraphs = 0

    for tag, i1, i2, j1, j2 in paragraph_matcher.get_opcodes():
        if tag == "insert":
            added_paragraphs += j2 - j1
        elif tag == "delete":
            removed_paragraphs += i2 - i1
        elif tag == "replace":
            modified_paragraphs += max(i2 - i1, j2 - j1)

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "modified_blocks": modified_blocks,
        "added_paragraphs": added_paragraphs,
        "removed_paragraphs": removed_paragraphs,
        "modified_paragraphs": modified_paragraphs,
    }


def build_change_summary_text(summary: dict) -> str:
    return (
        "新增段落: {added_paragraphs}, 删除段落: {removed_paragraphs}, 改写段落: {modified_paragraphs}; "
        "新增行: {added_lines}, 删除行: {removed_lines}, 改写块: {modified_blocks}"
    ).format(**summary)


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
