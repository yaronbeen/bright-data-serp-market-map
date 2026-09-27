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


def test_dry_run_rejects_blank_queries_before_planning(capsys):
    assert market_map.main(["--query", "valid query", "--query", "", "--dry-run"]) == 2
    assert "query cannot be blank" in capsys.readouterr().err


def test_synthesis_adds_intent_and_observed_content_gaps():
    rows = market_map.normalize({"organic": [
        {"title": "Best CRM tools compared", "link": "https://a.example/compare", "global_rank": 1},
        {"title": "CRM pricing plans", "link": "https://b.example/pricing", "global_rank": 2},
    ]}, "best CRM pricing", "us", "en")
    report = market_map.synthesize(rows)
    query = report["queries"][0]
    assert query["intent"] == "commercial_investigation"
    assert "how_to_guide" in query["unobserved_content_formats"]
    assert report["market_competitors"]
    assert "returned SERP sample" in report["caveat"]


def test_organic_rank_uses_rank_not_global_rank_or_list_fallback():
    rows = market_map.normalize({"organic": [
        {"link": "https://a.example", "rank": 2, "global_rank": 7},
        {"link": "https://b.example", "global_rank": 8},
    ]}, "query")
    assert [row["position"] for row in rows] == [2, 2]


def test_deduplicates_fragment_and_host_variant():
    rows = market_map.normalize({"organic": [
        {"link": "https://www.example.com/path#one", "rank": 1},
        {"link": "https://example.com/path#two", "rank": 2},
    ]}, "query")
    assert len(rows) == 1


def test_rejects_invalid_locale_before_any_request(monkeypatch, capsys):
    monkeypatch.setattr(market_map, "request_serp", lambda *args: (_ for _ in ()).throw(AssertionError("request happened before validation")))
    assert market_map.main(["--query", "first", "--query", "second", "--country", "USA"]) == 2


def test_csv_formula_values_are_neutralized(tmp_path):
    rows = market_map.normalize({"organic": [{"link": "https://example.com", "title": "=HYPERLINK(\"x\")"}]}, "query")
    market_map.write_csv(tmp_path / "safe.csv", rows)
    assert "'=HYPERLINK" in (tmp_path / "safe.csv").read_text()
