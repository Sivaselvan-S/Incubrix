"""Tests for Batch Runner CLI (cli.batch_runner)."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cli.batch_runner import (
    collect_input_files,
    parse_json_file,
    parse_markdown_file,
)


def test_parse_markdown_with_frontmatter():
    """Verifies YAML frontmatter and body extraction from markdown."""
    with TemporaryDirectory() as tmp_dir:
        md_file = Path(tmp_dir) / "article-1.md"
        md_file.write_text(
            """---
title: "Autonomous Distribution Networks"
destination_id: "dest_devto_001"
canonical_url: "https://example.com/original"
tags: [ai, python, devops]
---
# Main Heading

Here is the markdown content body describing the architecture.
""",
            encoding="utf-8",
        )

        parsed = parse_markdown_file(md_file)
        assert parsed["title"] == "Autonomous Distribution Networks"
        assert parsed["destination_id"] == "dest_devto_001"
        assert parsed["canonical_url"] == "https://example.com/original"
        assert "ai" in parsed["tags"]
        assert "Here is the markdown content body" in parsed["body"]


def test_parse_markdown_without_frontmatter():
    """Verifies title fallback to first heading and filename."""
    with TemporaryDirectory() as tmp_dir:
        md_file = Path(tmp_dir) / "simple-post.md"
        md_file.write_text(
            """# Pure Heading Title

This is a post without any frontmatter.
""",
            encoding="utf-8",
        )

        parsed = parse_markdown_file(md_file)
        assert parsed["title"] == "Pure Heading Title"
        assert "This is a post without any frontmatter." in parsed["body"]


def test_parse_json_file():
    """Verifies direct JSON file parsing."""
    with TemporaryDirectory() as tmp_dir:
        json_file = Path(tmp_dir) / "item.json"
        json_file.write_text(
            json.dumps({
                "title": "JSON Defined Post",
                "body": "Body from JSON definition",
                "destination_id": "dest_gh_01",
                "tags": ["fastapi", "testing"],
            }),
            encoding="utf-8",
        )

        parsed = parse_json_file(json_file)
        assert parsed["title"] == "JSON Defined Post"
        assert parsed["body"] == "Body from JSON definition"
        assert parsed["destination_id"] == "dest_gh_01"
        assert parsed["tags"] == ["fastapi", "testing"]


def test_collect_input_files():
    """Verifies file discovery across directories and single files."""
    with TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir)
        (p / "f1.md").write_text("# F1", encoding="utf-8")
        (p / "f2.markdown").write_text("# F2", encoding="utf-8")
        (p / "f3.json").write_text("{}", encoding="utf-8")
        (p / "ignored.txt").write_text("text", encoding="utf-8")

        collected = collect_input_files(p)
        stems = [f.stem for f in collected]
        assert "f1" in stems
        assert "f2" in stems
        assert "f3" in stems
        assert "ignored" not in stems
