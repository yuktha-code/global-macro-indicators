import pytest
import requests
from econpipe.api import WorldBankClient, SourceAPIError


class Response:
    def __init__(self, json_value, status=200):
        self.json_value = json_value
        self.status = status
    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))
    def json(self):
        return self.json_value

class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return next(self.responses)


def test_pagination_read_every_page():
    session = Session([
        Response([{"page": 1, "pages": 2, "total": 3}, [{"id": "A"}, {"id": "B"}]]),
        Response([{"page": 2, "pages": 2, "total": 3}, [{"id": "C"}]])
    ])
    result = WorldBankClient(session=session, per_page=2).pages("/country")
    assert [r["id"] for r in result] == ["A", "B", "C"]
    assert [c[1]["page"] for c in session.calls] == [1, 2]
    assert all(c[1]["format"] == "json" for c in session.calls)


def test_incomplete_page_fails_without_silent_success():
    session = Session([Response([{"page": 1, "pages": 1, "total": 3}, [{"id": "A"}]])])
    with pytest.raises(SourceAPIError, match="Incomplete"):
        WorldBankClient(session=session).pages("/country")


def test_http_failure_propagated():
    with pytest.raises(SourceAPIError, match="request failed"):
        WorldBankClient(session=Session([Response(None, status=503)])).pages("/country")


def test_malformed_api_json_errors():
    with pytest.raises(SourceAPIError, match="Unexpected"):
        WorldBankClient(session=Session([Response({"error": "invalid"})])).pages("/country")


def test_mutating_pagination_errors():
    session = Session([Response([{"page": 1, "pages": 2, "total": 2}, [{"x": 1}]]),
                       Response([{"page": 2, "pages": 3, "total": 2}, [{"x": 2}]])])
    with pytest.raises(SourceAPIError, match="Page count changed"):
        WorldBankClient(session=session).pages("/country")
