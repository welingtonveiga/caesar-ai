"""Tools and production integrations for reading the web."""

from collections.abc import Sequence
from typing import Protocol

import httpx
from ddgs import DDGS
from markdownify import markdownify

from caesar.tools.types import Tier, Tool, ToolContext


class SearchBackend(Protocol):
    """The result shape Caesar needs from a web search provider."""

    def text(
        self,
        query: str,
        *,
        max_results: int,
    ) -> list[dict[str, str]]: ...


class WebAccessToolset:
    """Build web tools backed by the production HTTP and search integrations."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        search_backend: SearchBackend | None = None,
    ) -> None:
        self._transport = transport
        self._search_backend = search_backend

    def list_tools(self, context: ToolContext) -> Sequence[Tool]:
        del context

        def web_fetch(url: str) -> str:
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

        def web_search(query: str) -> str:
            backend = self._search_backend or DDGS()
            results = backend.text(query, max_results=5)
            return "\n\n".join(
                f"{number}. [{result['title']}]({result['href']})\n   {result['body']}"
                for number, result in enumerate(results, start=1)
            )

        return (
            Tool(
                name="web_fetch",
                description="Fetch a web page and return its readable content.",
                tier=Tier.ONE,
                function=web_fetch,
            ),
            Tool(
                name="web_search",
                description="Search the web and return relevant results.",
                tier=Tier.ONE,
                function=web_search,
            ),
        )
