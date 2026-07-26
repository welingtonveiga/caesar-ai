"""Production web client behavior without live network access."""

import httpx

from caesar.tools import DefaultWebClient
from tests.support.fake_web_client import FakeSearchBackend


def test_fetch_returns_markdown_for_an_html_page():
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

    web_client = DefaultWebClient(transport=httpx.MockTransport(respond))

    result = web_client.fetch("https://example.com/report")

    assert result == "# Campaign report\n\nVictory."


def test_search_returns_concise_markdown_results():
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
    web_client = DefaultWebClient(search_backend=search_backend)

    result = web_client.search("Roman roads")

    assert result == (
        "1. [Via Appia](https://example.com/appia)\n   Ancient Roman road."
    )
    assert search_backend.queries == [("Roman roads", 5)]
