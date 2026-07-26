"""Tools and production integrations for reading the web."""

from collections.abc import Sequence
from typing import Protocol

import httpx
from ddgs import DDGS
from markdownify import markdownify

from caesar.tools.types import Tier, ToolContext, ToolDefinition


class SearchBackend(Protocol):
    """The result shape Caesar needs from a web search provider."""

    def text(
        self,
        query: str,
        *,
        max_results: int,
    ) -> list[dict[str, str]]: ...


class DefaultWebClient:
    """Fetch web content using the built-in production integrations."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        search_backend: SearchBackend | None = None,
    ) -> None:
        self._transport = transport
        self._search_backend = search_backend

    def fetch(self, url: str) -> str:
        with httpx.Client(
            transport=self._transport,
            follow_redirects=True,
            timeout=10,
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        if "text/html" in response.headers.get("content-type", ""):
            return markdownify(response.text, heading_style="ATX").strip()
        return response.text

    def search(self, query: str) -> str:
        backend = self._search_backend or DDGS()
        results = backend.text(query, max_results=5)
        return "\n\n".join(
            f"{number}. [{result['title']}]({result['href']})\n   {result['body']}"
            for number, result in enumerate(results, start=1)
        )


class WebAccessToolset:
    """Build web tools with the trusted web client captured from the engine."""

    def list_tools(self, context: ToolContext) -> Sequence[ToolDefinition]:
        def web_fetch(url: str) -> str:
            return context.web_client.fetch(url)

        def web_search(query: str) -> str:
            return context.web_client.search(query)

        return (
            ToolDefinition(
                name="web_fetch",
                description="Fetch a web page and return its readable content.",
                tier=Tier.ONE,
                function=web_fetch,
            ),
            ToolDefinition(
                name="web_search",
                description="Search the web and return relevant results.",
                tier=Tier.ONE,
                function=web_search,
            ),
        )
