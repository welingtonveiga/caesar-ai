"""Deterministic web client double for tool and graph tests."""


class FakeWebClient:
    def __init__(
        self,
        pages: dict[str, str],
        searches: dict[str, str] | None = None,
    ) -> None:
        self.pages = pages
        self.searches = searches or {}
        self.fetched_urls: list[str] = []
        self.searched_queries: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetched_urls.append(url)
        return self.pages[url]

    def search(self, query: str) -> str:
        self.searched_queries.append(query)
        return self.searches[query]


class FakeSearchBackend:
    def __init__(self, results: dict[str, list[dict[str, str]]]) -> None:
        self.results = results
        self.queries: list[tuple[str, int]] = []

    def text(self, query: str, max_results: int) -> list[dict[str, str]]:
        self.queries.append((query, max_results))
        return self.results[query]
