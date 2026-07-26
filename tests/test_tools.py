"""Tier classification for Caesar's built-in tools."""

import pytest

from caesar.tools import Tier, read_file, web_fetch, web_search, write_file
from tests.support.fake_web_client import FakeWebClient


def test_local_file_tools_are_tier_one_capabilities():
    assert read_file.tier is Tier.ONE
    assert write_file.tier is Tier.ONE


def test_web_tools_are_tier_one_capabilities():
    assert web_fetch.tier is Tier.ONE
    assert web_search.tier is Tier.ONE


def test_web_fetch_uses_the_supplied_web_client():
    web_client = FakeWebClient(pages={"https://example.com/report": "Campaign report"})

    result = web_fetch.run(
        web_client=web_client,
        url="https://example.com/report",
    )

    assert result == "Campaign report"
    assert web_client.fetched_urls == ["https://example.com/report"]


def test_web_search_uses_the_supplied_web_client():
    web_client = FakeWebClient(
        pages={},
        searches={"Roman roads": "1. Via Appia\n2. Via Flaminia"},
    )

    result = web_search.run(web_client=web_client, query="Roman roads")

    assert result == "1. Via Appia\n2. Via Flaminia"
    assert web_client.searched_queries == ["Roman roads"]


def test_read_file_reads_from_the_agent_filesystem(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()
    (filesystem / "notes.txt").write_text("Cross the Rubicon.")

    result = read_file.run(
        agent_dir=tmp_path,
        path="filesystem/notes.txt",
    )

    assert result == "Cross the Rubicon."


def test_read_file_rejects_path_traversal_outside_allowed_folders(tmp_path):
    secret_file = tmp_path.parent / "secret.txt"
    secret_file.write_text("classified")

    with pytest.raises(ValueError, match="outside allowed directories"):
        read_file.run(
            agent_dir=tmp_path,
            path="../secret.txt",
        )


def test_read_file_rejects_a_symlink_to_an_outside_file(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()
    secret_file = tmp_path.parent / "symlink-secret.txt"
    secret_file.write_text("classified")
    (filesystem / "shortcut.txt").symlink_to(secret_file)

    with pytest.raises(ValueError, match="outside allowed directories"):
        read_file.run(
            agent_dir=tmp_path,
            path="filesystem/shortcut.txt",
        )


def test_read_file_allows_configured_extra_folders(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "data.csv").write_text("a,b,c")

    result = read_file.run(
        agent_dir=agent_dir,
        path=str(external_dir / "data.csv"),
        allowed_folders=[external_dir],
    )

    assert result == "a,b,c"


def test_write_file_writes_inside_the_agent_filesystem(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()

    result = write_file.run(
        agent_dir=tmp_path,
        path="filesystem/summary.txt",
        content="The campaign is complete.",
    )

    assert result == "Wrote filesystem/summary.txt"
    assert (filesystem / "summary.txt").read_text() == "The campaign is complete."


def test_write_file_rejects_paths_outside_the_agent_filesystem(tmp_path):
    (tmp_path / "filesystem").mkdir()

    with pytest.raises(ValueError, match="outside allowed directories"):
        write_file.run(
            agent_dir=tmp_path,
            path="outside.txt",
            content="This must not be written.",
        )

    assert not (tmp_path / "outside.txt").exists()
