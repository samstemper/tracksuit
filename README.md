# Market Diffusion via Google Trends

This workspace starts a reproducible analysis for the hypothesis that product trends diffuse across markets faster now than they used to.

The first case study is drink bottles. The active analysis uses a defined `anglophone6_local_category_2004` country panel: Australia, Canada, Ireland, New Zealand, the United Kingdom, and the United States. Raw Google Trends data is collected from 2004 onward, while the processed analysis removes pre-2010 observations. New Zealand and Australia use `drink bottle`; the other countries use `water bottle`. For each brand, the query follows a consistent `{brand} {local bottle category}` convention and is pulled together with the matching category baseline, then analyzed as the ratio:

```text
relative_interest = trailing_3_month_avg(brand_local_category_search_index)
                  / trailing_3_month_avg(local_category_search_index)
```

The charted brand-month series is the average of that country-month ratio across available countries, including zeros.

Trend start rule: first month where the brand-month average is at least 0.0025 and at least 9 of the next 12 months are also at or above 0.0025.

## Run

```bash
python3 scripts/google_trends_diffusion.py --collect --analyze --charts
```

## Website

The static site is built from the processed CSVs and can be served directly from GitHub Pages.

```bash
python3 -m http.server 8001
```

Then open `http://localhost:8001`. The included `CNAME` points GitHub Pages at `tracksuit.samstemper.com` once DNS is configured.

Outputs:

- `data/raw/anglophone6_local_category_2004/`: one CSV per trend/country pull from Google Trends for the active panel
- `data/processed/trends_panel.csv`: long country-month panel with ratios and scores
- `data/processed/brand_month_average_interest.csv`: average ratio by brand-month
- `data/processed/brand_month_cumulative_since_2010.csv`: cumulative brand-month series since 2010
- `data/processed/trend_start_dates.csv`: detected start date by brand
- `data/processed/brand_month_event_time.csv`: brand-month series with months before/after start
- `data/processed/brand_month_cumulative_event_time.csv`: cumulative brand-month series from 24 months before trend start, indexed to zero at trend start
- `charts/average_normalized_interest_by_brand.png`: facets on a shared y-axis with start dates marked
- `charts/cumulative_average_interest_since_2010_by_brand.png`: cumulative facets since 2010 with start dates marked
- `charts/average_interest_overlay_by_brand.png`: all brands on calendar time with different colors
- `charts/event_time_average_interest_by_brand.png`: all brands on months before/after trend start
- `charts/cumulative_event_time_average_interest_by_brand.png`: cumulative average intensity by months since trend start

## Notes

Google Trends has no official public API, so this uses `pytrends`. Raw Trends scores are normalized per request; to reduce that issue, every request compares one brand term against the same baseline term in the same country/timeframe. The analysis should be interpreted as directional evidence, not a definitive market-size estimate.

Collection is batched by country: each Google Trends request includes up to 4 brand queries plus the local category baseline. The collector then writes one CSV per brand-country so the analysis pipeline stays simple.

The active brand queries are:

- `{brand} drink bottle` in Australia and New Zealand
- `{brand} water bottle` in Canada, Ireland, the United Kingdom, and the United States
