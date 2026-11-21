"""Backoff nos providers: só falha transitória se repetida, sem inventar dado."""

import httpx
import pytest

from core.exceptions import DataInsufficientError
from core.retry import retry_request
from data.providers.brapi import BrapiProvider


def response(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", "https://example.test"))


def test_retries_transient_status_then_returns():
    answers = iter([response(503), response(200)])
    pauses = []

    result = retry_request(lambda: next(answers), sleep=pauses.append)

    assert result.status_code == 200
    assert len(pauses) == 1
    assert 0.25 <= pauses[0] <= 0.25 * 1.2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429])
def test_does_not_retry_permanent_status(status):
    calls = []
    pauses = []

    def call():
        calls.append(status)
        return response(status)

    assert retry_request(call, sleep=pauses.append).status_code == status
    assert calls == [status]
    assert pauses == []


def test_retries_transport_error_then_returns():
    attempts = []

    def call():
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise httpx.ConnectTimeout("lento")
        return response(200)

    assert retry_request(call, sleep=lambda _: None).status_code == 200
    assert len(attempts) == 2


def test_reraises_transport_error_after_last_attempt():
    attempts = []

    def call():
        attempts.append(len(attempts))
        raise httpx.ReadTimeout("lento")

    with pytest.raises(httpx.ReadTimeout):
        retry_request(call, sleep=lambda _: None)
    assert len(attempts) == 3


def test_attempts_one_skips_retry():
    pauses = []
    assert retry_request(lambda: response(503), attempts=1, sleep=pauses.append).status_code == 503
    assert pauses == []


def test_invalid_attempts():
    with pytest.raises(ValueError, match="attempts"):
        retry_request(lambda: response(200), attempts=0)


def test_brapi_recovers_from_transient_failure():
    attempts = []

    def handler(request):
        attempts.append(request.url.path)
        if len(attempts) == 1:
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "data": {
                            "regularMarketPrice": 40.0,
                            "regularMarketTime": "2026-11-03T14:00:00Z",
                        }
                    }
                ]
            },
        )

    provider = BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    snapshot = provider.get_market_snapshot("PETR4")

    assert snapshot.price == 40.0
    assert len(attempts) == 2


def test_brapi_keeps_missing_data_as_insufficient():
    provider = BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))))
    with pytest.raises(DataInsufficientError):
        provider.get_market_snapshot("PETR4")
