from app.data.provider_service import MarketDataService


class DummyProvider:
    def __init__(self):
        self.calls = 0

    def get_quote(self, symbol):
        self.calls += 1
        return {"c": 100.0, "dp": 1.2}


def test_quote_cache():
    svc = MarketDataService()
    dummy = DummyProvider()
    svc._provider = lambda source, api_key: dummy  # type: ignore[method-assign]

    a = svc.get_quote("finnhub", "k", "AAPL", ttl=30)
    b = svc.get_quote("finnhub", "k", "AAPL", ttl=30)
    assert a["c"] == 100.0
    assert b["dp"] == 1.2
    assert dummy.calls == 1
