# Bright Data SERP Query Opportunity Map

**Repository:** [bright-data-serp-market-map](https://github.com/yaronbeen/bright-data-serp-market-map) · **Data provider:** [Bright Data](https://brightdata.com/)

**Before you plan another SEO page, see what a small, deliberate set of Google searches actually returns.** SERP Query Opportunity Map turns those results into an evidence-linked brief: query intent, domains appearing across queries, observed title formats, and formats not seen in the returned sample. It helps a marketer choose what competitor or content question to inspect next; it does not estimate traffic, market share, or ranking outcomes.

## Use cases and architecture

Compare competitors across a deliberately scoped set of commercial, transactional, and informational queries; inspect query intent, domain overlap, and which title-level content formats appeared in the bounded result sample. Flow: `queries + locale -> Bright Data SERP API -> intent/archetype classification -> query opportunity brief`. Runtime uses Python 3.10+ standard library.

## Example: query set to content research decision

A content lead is evaluating a CRM topic for US English search. They run a few deliberately chosen queries, such as a comparison query and a how-to query, then review which domains recur and which title-level formats appear in the returned organic results.

Synthetic illustration: a competitor domain appears in 4 of 6 scoped query result sets, while no pricing-format title is observed for one query. That suggests two manual follow-ups: inspect the competitor pages and check whether a useful pricing page could answer the uncovered query. It does **not** mean the competitor owns two-thirds of the market, that searchers want a pricing page, or that publishing one will rank. “Not observed” means only absent from this returned sample.

Offline request preview:

```bash
python3 market_map.py --query "best CRM for small teams" \\
  --query "CRM onboarding guide" --country us --language en --dry-run
```

Dry-run validates parameters and prints the number of requests planned without calling Bright Data. A real run writes the normalized SERP results and synthesis to JSON by default; CSV contains normalized result rows only.

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

JSON contains normalized `results`, query-level `intent`, observed content formats, `content_opportunities` marked `not_observed_in_returned_sample`, cross-query `market_competitors`, and a caveat. Organic `position` uses the organic rank or one-based position in the returned organic list; `global_rank` is retained separately when supplied. Result rows include query intent, format, locale, ranks, title, URL, domain, snippet, and UTC `observed_at`. CSV exports result rows only; synthesis summaries and caveats are in JSON. These are opportunity prompts from a bounded result sample, not proof of a market gap; missing formats may simply rank below the returned results. Formula-leading scraped text is prefixed in CSV exports to reduce spreadsheet formula injection risk.

Illustrative decision: a domain found across 4 of 6 scoped queries may merit manual competitor review; a `pricing` title format not observed for one query may suggest a content question to investigate. Neither count is market share, and absence from returned results does not prove absence from the market.

## How this differs from existing tools

Unlike `bright-data-google-search-scraper`, which focuses on general SERP collection/export across engines, this Google-focused tool synthesizes a small query set into intent buckets, cross-query domain overlap, and title-format prompts for a marketer’s next research action. It does not measure ChatGPT/AI brand visibility like `bright-data-chatgpt-visibility-checker`. Classification is literal/title-level, not a page-content audit or ranked recommendation engine.

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

Offline tests cover parsing, URL validation, duplicate normalization, locale carry-through, intent classification, content archetypes, opportunity labeling, and query-aware competitor summaries. MIT License.

## FAQ

**Does this tool check my site's rankings or traffic?** No. It records returned SERP results for each query. It does not estimate search volume, traffic, ranking probability, or outcomes.

**What does a content opportunity mean?** A supported title-format category not observed in the returned results for that query. Treat it as a prompt to inspect the SERP and user need, not as proof of a market gap.

**Can I use it offline?** You can run dry-run and the test suite locally. Producing a live market map requires Bright Data SERP API credentials and a configured SERP zone; each query is a separate request and may be billable.

**Why specify country and language?** SERPs vary by locale. Those values are attached to each result so comparisons retain the context in which they were collected.
