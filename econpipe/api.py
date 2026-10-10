"""Official World Bank v2 API client with paging, retry and explicit failure handling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.worldbank.org/v2"


class SourceAPIError(RuntimeError):
    """Raised when upstream payload/transport is malformed or unavailable."""


@dataclass
class WorldBankClient:
    session: Any = None
    timeout: int = 20
    per_page: int = 1000

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            retry = Retry(total=4, connect=4, read=3, status=3,
                          status_forcelist=[429, 500, 502, 503, 504],
                          backoff_factor=0.6, allowed_methods=frozenset(["GET"]))
            self.session.mount("https://", HTTPAdapter(max_retries=retry))
        if not (1 <= self.per_page <= 20000):
            raise ValueError("per_page must be between 1 and 20000")

    def pages(self, route: str, params: dict[str, str | int] | None = None) -> list[dict]:
        """Read *every* page and raise rather than silently returning partial data."""
        if not route.startswith("/") or ".." in route:
            raise ValueError("Invalid World Bank route")
        url = BASE_URL + route
        records: list[dict] = []
        page = 1
        expected_pages: int | None = None
        while True:
            kwargs = {**(params or {}), "format": "json", "page": page, "per_page": self.per_page}
            try:
                response = self.session.get(url, params=kwargs, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise SourceAPIError(f"World Bank request failed at {route} page {page}: {exc}") from exc
            if not isinstance(payload, list) or len(payload) != 2:
                raise SourceAPIError(f"Unexpected World Bank response at {route}, page {page}")
            info, batch = payload
            if not isinstance(info, dict) or not isinstance(batch, list):
                raise SourceAPIError("Response missing page metadata or record list")
            try:
                got_page = int(info["page"])
                pages = int(info["pages"])
                total = int(info["total"])
            except (KeyError, ValueError, TypeError) as exc:
                raise SourceAPIError("Invalid page metadata") from exc
            if got_page != page or pages < 1 or total < 0:
                raise SourceAPIError("Inconsistent page metadata")
            if expected_pages is None:
                expected_pages = pages
            elif pages != expected_pages:
                raise SourceAPIError("Page count changed during ingestion; retry later")
            if not all(isinstance(item, dict) for item in batch):
                raise SourceAPIError("Nonobject API record")
            records.extend(batch)
            if page >= pages:
                break
            page += 1
        if len(records) != total:
            raise SourceAPIError(f"Incomplete API response: expected {total}, got {len(records)}")
        return records

    def countries(self, codes: tuple[str, ...]) -> list[dict]:
        # Explicit codes prevent regional aggregates and bound the dataset.
        return self.pages("/country/" + ";".join(codes))

    def indicator(self, code: str) -> list[dict]:
        return self.pages("/indicator/" + code, {"source": 2})

    def observations(self, codes: tuple[str, ...], indicator: str,
                     first_year: int, last_year: int) -> list[dict]:
        return self.pages("/country/" + ";".join(codes) + "/indicator/" + indicator,
                          {"date": f"{first_year}:{last_year}", "source": 2})
