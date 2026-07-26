"""Built-in tool declarations and their governance tiers."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

import httpx
from ddgs import DDGS
from markdownify import markdownify


class Tier(Enum):
    """A tool's execution policy.

    ONE executes immediately, TWO executes autonomously in a sandbox, and
    THREE requires explicit user approval before execution.
    """

    ONE = 1
    TWO = 2
    THREE = 3


class WebClient(Protocol):
    """The web operations required by Caesar's web tools."""

    def fetch(self, url: str) -> str: ...

    def search(self, query: str) -> str: ...


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


@dataclass(frozen=True)
class Tool:
    """A built-in tool's stable identity and approval policy."""

    name: str
    tier: Tier
    func: Callable[..., str]

    def run(self, **kwargs: object) -> str:
        return self.func(**kwargs)


def _ensure_contained(
    target: Path,
    allowed_roots: Sequence[Path],
    original_path: str,
) -> Path:
    resolved = target.resolve()
    for root in allowed_roots:
        resolved_root = root.resolve()
        if resolved.is_relative_to(resolved_root):
            return resolved
    raise ValueError(
        f"Access denied: path '{original_path}' is outside allowed directories"
    )


def _read_file(
    agent_dir: Path,
    path: str,
    allowed_folders: Sequence[Path] = (),
) -> str:
    target = agent_dir / path
    allowed = [agent_dir, *allowed_folders]
    contained_path = _ensure_contained(target, allowed, path)
    return contained_path.read_text()


def _write_file(agent_dir: Path, path: str, content: str) -> str:
    target = _ensure_contained(
        agent_dir / path,
        [agent_dir / "filesystem"],
        path,
    )
    target.write_text(content)
    return f"Wrote {path}"


def _web_fetch(web_client: WebClient, url: str) -> str:
    return web_client.fetch(url)


def _web_search(web_client: WebClient, query: str) -> str:
    return web_client.search(query)


read_file = Tool("read_file", Tier.ONE, func=_read_file)
write_file = Tool("write_file", Tier.ONE, func=_write_file)
web_fetch = Tool("web_fetch", Tier.ONE, func=_web_fetch)
web_search = Tool("web_search", Tier.ONE, func=_web_search)
