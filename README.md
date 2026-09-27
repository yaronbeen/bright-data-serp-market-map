# SERP Market Map

A marketer-facing CLI for turning a small set of Bright Data Google SERPs into an evidence-linked view of domains, result positions, titles, and snippets. Domain frequency is a snapshot description, not a traffic estimate or SEO forecast.

## Use cases and architecture

Compare who appears for a set of buyer-intent, category, and content queries; identify recurring cited domains and inspect pages manually for gaps. Flow: `query + locale -> Bright Data SERP API -> normalized organic rows -> domain frequency summary -> JSON/CSV`. Runtime uses Python 3.10+ standard library.

## Setup

Create a SERP API in the [Bright Data control panel](https://brightdata.com/cp/start) following [Create your first SERP API](https://docs.brightdata.com/products/serp-api/quickstart). The API name is the zone. Create an API key in [account settings](https://brightdata.com/cp/setting/users), then set:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export BRIGHT_DATA_API_KEY='your-key'
export BRIGHT_DATA_SERP_ZONE='your-serp-api-name'
```

`.env.example` lists names only; the CLI intentionally reads process environment rather than silently loading secrets. API behavior is based on official [SERP API docs](https://docs.brightdata.com/scraping-automation/serp-api/introduction), [request API](https://docs.brightdata.com/api-reference/rest-api/serp/serp-api.md), [parsed JSON response schema](https://docs.brightdata.com/products/serp-api/parsed-json-results.md), and [billing](https://docs.brightdata.com/products/serp-api/pricing-and-billing). The CLI uses the documented direct `POST https://api.brightdata.com/request` contract with `zone`, Google query URL, and `format: json` for structured SERP data.

## Run

```bash
python market_map.py --query "best CRM for small teams" --query "CRM onboarding guide" --country us --language en --output map.json
python market_map.py --query "project management software" --output map.csv
python market_map.py --query "CRM for agencies" --dry-run
```

Dry-run prints planned request count and sends no HTTP request. Each query is a separate request; keep query counts and result depth bounded. Pricing/billing can change; consult the [current SERP billing docs](https://docs.brightdata.com/products/serp-api/pricing-and-billing) and account plan before collecting. No result cache or retry loop obscures request volume.

## Output

JSON contains normalized `results`, a `domain_summary` grouped by both query and domain, and a caveat. Summary rows contain `query`, `domain`, and `results` count so recurring visibility does not erase the query context. Result rows contain `query`, `country`, `language`, `position`, `title`, `url`, `domain`, `snippet`, and UTC `observed_at`. CSV emits result rows. Missing snippets are empty. Duplicate canonical host/path results are removed per query response. The sample fixture is illustrative and is used by the offline parser tests.

## Caveats and ethical use

Search rankings change with time, engine, locale, device, and personalization. Sparse appearances or high frequency do not establish market share, search volume, traffic, or content opportunity. Validate actual pages and strategy independently. Use only in ways permitted by your Bright Data agreement and applicable law; store only data needed for research and honor retention needs.

## Troubleshooting and tests

- Zone missing: create SERP API and export its name as `BRIGHT_DATA_SERP_ZONE`.
- 401/403: confirm API key and zone permissions.
- 429: reduce request rate and review current rate limits; do not retry rapidly.
- Empty SERP: verify locale, query encoding, and Bright Data response format.
- Malformed result links and unsupported schemes are rejected rather than assigned a guessed domain; HTTP and HTTPS destinations are both preserved as evidence.

```bash
python3 -m pytest -q
```

Offline tests cover parsing, URL validation, duplicate normalization, locale carry-through, and domain summaries. MIT License.
