"""Deterministic search backend double for web tool tests."""


class FakeSearchBackend:
    def __init__(self, results: dict[str, list[dict[str, str]]]) -> None:
        self.results = results
        self.queries: list[tuple[str, int]] = []

    def text(self, query: str, max_results: int) -> list[dict[str, str]]:
        self.queries.append((query, max_results))
        return self.results[query]
