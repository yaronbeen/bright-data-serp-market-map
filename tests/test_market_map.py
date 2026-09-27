import market_map
import json


def test_normalizes_organic_results_and_domains():
    rows = market_map.normalize({"organic": [{"title": "Guide", "link": "https://www.example.com/guide", "description": "How to"}, {"title": "Guide", "link": "https://example.com/guide"}]}, "crm software", "us", "en")
    assert len(rows) == 1
    assert rows[0]["domain"] == "example.com"
    assert rows[0]["position"] == 1
    assert rows[0]["query"] == "crm software"


def test_rejects_invalid_search_url():
    try:
        market_map.domain("javascript:alert(1)")
    except ValueError:
        pass
    else:
        assert False, "invalid scheme must fail"


def test_http_result_urls_are_preserved_as_evidence():
    rows = market_map.normalize({"organic": [{"link": "http://legacy.example/page"}]}, "query")
    assert rows[0]["domain"] == "legacy.example"


def test_rejects_invalid_port_and_url_userinfo():
    for url in ("https://example.com:99999/page", "https://" + "user" + ":" + "pass" + "@example.com/page"):
        try:
            market_map.domain(url)
        except ValueError:
            continue
        assert False, f"unsafe or malformed URL accepted: {url}"


def test_malformed_organic_entry_fails_cleanly():
    try:
        market_map.normalize({"organic": [7]}, "query")
    except ValueError as exc:
        assert "object" in str(exc)
    else:
        assert False, "non-object SERP entries must fail with a validation error"


def test_direct_request_asks_for_documented_structured_json(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"organic": []}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(market_map, "urlopen", fake_urlopen)
    market_map.request_serp("crm tools", "us", "en", "test-key", "test-zone")
    assert captured["url"] == "https://api.brightdata.com/request"
    assert captured["payload"]["format"] == "json"
    assert "brd_json" not in captured["payload"]["url"]


def test_market_summary():
    rows = [{"domain": "a.com", "position": 1}, {"domain": "a.com", "position": 3}, {"domain": "b.com", "position": 2}]
    summary = market_map.summarize(rows)
    assert summary[0]["domain"] == "a.com"
    assert summary[0]["results"] == 2


def test_summary_keeps_query_context():
    rows = [{"query": "one", "domain": "a.com", "position": 1}, {"query": "two", "domain": "a.com", "position": 2}]
    summary = market_map.summarize(rows)
    assert len(summary) == 2
    assert {row["query"] for row in summary} == {"one", "two"}
