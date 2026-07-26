"""Tier classification for Caesar's built-in tools."""

import pytest
from langchain_core.tools import StructuredTool

from caesar.tools import (
    Tier,
    Tool,
    ToolContext,
    list_tools,
)


def test_tool_executes_its_function_with_supplied_arguments():
    def greet(name: str) -> str:
        return f"Ave, {name}."

    tool = Tool(
        name="greet",
        description="Greet someone.",
        tier=Tier.ONE,
        function=greet,
    )

    assert tool.execute(name="Caesar") == "Ave, Caesar."


def configured_tools(tmp_path, *, folders=()):
    return {
        tool.name: tool
        for tool in list_tools(
            ToolContext(
                agent_dir=tmp_path,
                folders=folders,
            )
        )
    }


def test_listed_tool_defines_governance_and_model_schema(tmp_path):
    tools = configured_tools(tmp_path)

    read_tool = tools["read_file"]
    model_tool = StructuredTool.from_function(
        func=read_tool.function,
        name=read_tool.name,
        description=read_tool.description,
    )

    assert read_tool.tier is Tier.ONE
    assert set(model_tool.args) == {"path"}


def test_local_file_tools_are_tier_one_capabilities(tmp_path):
    tools = configured_tools(tmp_path)

    assert tools["read_file"].tier is Tier.ONE
    assert tools["write_file"].tier is Tier.ONE


def test_web_tools_are_tier_one_capabilities(tmp_path):
    tools = configured_tools(tmp_path)

    assert tools["web_fetch"].tier is Tier.ONE
    assert tools["web_search"].tier is Tier.ONE


def test_read_file_reads_from_the_agent_filesystem(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()
    (filesystem / "notes.txt").write_text("Cross the Rubicon.")

    result = configured_tools(tmp_path)["read_file"].execute(
        path="filesystem/notes.txt"
    )

    assert result == "Cross the Rubicon."


def test_read_file_rejects_path_traversal_outside_allowed_folders(tmp_path):
    secret_file = tmp_path.parent / "secret.txt"
    secret_file.write_text("classified")

    with pytest.raises(ValueError, match="outside allowed directories"):
        configured_tools(tmp_path)["read_file"].execute(path="../secret.txt")


def test_read_file_rejects_a_symlink_to_an_outside_file(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()
    secret_file = tmp_path.parent / "symlink-secret.txt"
    secret_file.write_text("classified")
    (filesystem / "shortcut.txt").symlink_to(secret_file)

    with pytest.raises(ValueError, match="outside allowed directories"):
        configured_tools(tmp_path)["read_file"].execute(path="filesystem/shortcut.txt")


def test_read_file_allows_configured_extra_folders(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "data.csv").write_text("a,b,c")

    result = configured_tools(agent_dir, folders=[external_dir])["read_file"].execute(
        path=str(external_dir / "data.csv")
    )

    assert result == "a,b,c"


def test_write_file_writes_inside_the_agent_filesystem(tmp_path):
    filesystem = tmp_path / "filesystem"
    filesystem.mkdir()

    result = configured_tools(tmp_path)["write_file"].execute(
        path="filesystem/summary.txt",
        content="The campaign is complete.",
    )

    assert result == "Wrote filesystem/summary.txt"
    assert (filesystem / "summary.txt").read_text() == "The campaign is complete."


def test_write_host_file_writes_inside_a_configured_folder(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    documents = tmp_path / "documents"
    documents.mkdir()

    result = configured_tools(agent_dir, folders=[documents])[
        "write_host_file"
    ].execute(
        path=str(documents / "summary.txt"),
        content="The campaign is complete.",
    )

    assert result == f"Wrote {documents / 'summary.txt'}"
    assert (documents / "summary.txt").read_text() == "The campaign is complete."


def test_write_file_rejects_paths_outside_the_agent_filesystem(tmp_path):
    (tmp_path / "filesystem").mkdir()

    with pytest.raises(ValueError, match="outside allowed directories"):
        configured_tools(tmp_path)["write_file"].execute(
            path="outside.txt",
            content="This must not be written.",
        )

    assert not (tmp_path / "outside.txt").exists()
