# Initial Findings

Threshold: country first crosses trend-normalized score >= 20.

Country panel: `anglophone6_local_category_2004` - English-speaking OECD countries: Australia, Canada, Ireland, New Zealand, United Kingdom, and United States. Australia and New Zealand use `drink bottle`; the other countries use `water bottle`.
Query convention: `{brand} {local bottle category}`. Baseline term is `drink bottle` in Australia/New Zealand and `water bottle` elsewhere.
Analysis transform: 3-month trailing average of brand index divided by 3-month trailing average of the local category baseline index.

## Diffusion Milestones

```text
              trend_slug trend_label  threshold start_date  start_year  countries_eventually_crossed  milestone_countries milestone_date months_to_milestone
   camelbak_water_bottle    CamelBak       20.0 2012-02-01        2012                             6                    5     2015-08-01                  42
   camelbak_water_bottle    CamelBak       20.0 2012-02-01        2012                             6                   10            NaT                <NA>
   camelbak_water_bottle    CamelBak       20.0 2012-02-01        2012                             6                   15            NaT                <NA>
   camelbak_water_bottle    CamelBak       20.0 2012-02-01        2012                             6                   20            NaT                <NA>
frank_green_water_bottle Frank Green       20.0 2021-01-01        2021                             2                    5            NaT                <NA>
frank_green_water_bottle Frank Green       20.0 2021-01-01        2021                             2                   10            NaT                <NA>
frank_green_water_bottle Frank Green       20.0 2021-01-01        2021                             2                   15            NaT                <NA>
frank_green_water_bottle Frank Green       20.0 2021-01-01        2021                             2                   20            NaT                <NA>
hydro_flask_water_bottle Hydro Flask       20.0 2016-08-01        2016                             4                    5            NaT                <NA>
hydro_flask_water_bottle Hydro Flask       20.0 2016-08-01        2016                             4                   10            NaT                <NA>
hydro_flask_water_bottle Hydro Flask       20.0 2016-08-01        2016                             4                   15            NaT                <NA>
hydro_flask_water_bottle Hydro Flask       20.0 2016-08-01        2016                             4                   20            NaT                <NA>
      owala_water_bottle       Owala       20.0 2023-03-01        2023                             6                    5     2025-09-01                  30
      owala_water_bottle       Owala       20.0 2023-03-01        2023                             6                   10            NaT                <NA>
      owala_water_bottle       Owala       20.0 2023-03-01        2023                             6                   15            NaT                <NA>
      owala_water_bottle       Owala       20.0 2023-03-01        2023                             6                   20            NaT                <NA>
    stanley_water_bottle     Stanley       20.0 2022-09-01        2022                             6                    5     2023-04-01                   7
    stanley_water_bottle     Stanley       20.0 2022-09-01        2022                             6                   10            NaT                <NA>
    stanley_water_bottle     Stanley       20.0 2022-09-01        2022                             6                   15            NaT                <NA>
    stanley_water_bottle     Stanley       20.0 2022-09-01        2022                             6                   20            NaT                <NA>
       yeti_water_bottle        Yeti       20.0 2011-10-01        2011                             3                    5            NaT                <NA>
       yeti_water_bottle        Yeti       20.0 2011-10-01        2011                             3                   10            NaT                <NA>
       yeti_water_bottle        Yeti       20.0 2011-10-01        2011                             3                   15            NaT                <NA>
       yeti_water_bottle        Yeti       20.0 2011-10-01        2011                             3                   20            NaT                <NA>
```

Interpretation caveats:

- Google Trends scores are sampled and normalized; rerunning can slightly change values.
- The denominator uses the local English category term, so this first pass is strongest for English-search-heavy markets.
- Brand queries use a consistent `{brand} {local bottle category}` convention to reduce cross-product query-composition differences.