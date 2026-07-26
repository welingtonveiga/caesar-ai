"""Production web tool behavior without live network access."""

import httpx

from caesar.tools import ToolContext, WebAccessToolset
from tests.support.fake_search_backend import FakeSearchBackend


def configured_tools(toolset, tmp_path):
    return {
        tool.name: tool
        for tool in toolset.list_tools(ToolContext(agent_dir=tmp_path, folders=()))
    }


def test_fetch_returns_markdown_for_an_html_page(tmp_path):
    def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="""
                <html>
                    <body><h1>Campaign report</h1><p>Victory.</p></body>
                    <script>stealSecrets()</script>
                </html>
            """,
        )

    tools = configured_tools(
        WebAccessToolset(transport=httpx.MockTransport(respond)), tmp_path
    )

    result = tools["web_fetch"].execute(url="https://example.com/report")

    assert result == "# Campaign report\n\nVictory."


def test_search_returns_concise_markdown_results(tmp_path):
    search_backend = FakeSearchBackend(
        {
            "Roman roads": [
                {
                    "title": "Via Appia",
                    "href": "https://example.com/appia",
                    "body": "Ancient Roman road.",
                }
            ]
        }
    )
    tools = configured_tools(WebAccessToolset(search_backend=search_backend), tmp_path)

    result = tools["web_search"].execute(query="Roman roads")

    assert result == (
        "1. [Via Appia](https://example.com/appia)\n   Ancient Roman road."
    )
    assert search_backend.queries == [("Roman roads", 5)]
