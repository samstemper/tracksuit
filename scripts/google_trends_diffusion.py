#!/usr/bin/env python3
"""Collect and analyze water-bottle trend diffusion using Google Trends."""

from __future__ import annotations

import argparse
import os
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pytrends.request import TrendReq


RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHART_DIR = ROOT / "charts"

DEFAULT_CATEGORY_TERM = "water bottle"
LOCAL_CATEGORY_TERMS = {
    "AU": "drink bottle",
    "NZ": "drink bottle",
}
TIMEFRAME = "2004-01-01 2026-06-28"
ANALYSIS_START_DATE = "2010-01-01"
COUNTRY_PANEL_NAME = "anglophone6_local_category_2004"
COUNTRY_PANEL_RULE = (
    "English-speaking OECD countries: Australia, Canada, Ireland, New Zealand, "
    "United Kingdom, and United States. Australia and New Zealand use `drink bottle`; "
    "the other countries use `water bottle`."
)
QUERY_CONVENTION = "{brand} {local bottle category}"
TREND_START_ABSOLUTE_THRESHOLD = 0.0025
TREND_START_WINDOW_MONTHS = 12
TREND_START_REQUIRED_ACTIVE_MONTHS = 9
MAX_TRENDS_PER_BATCH = 4


@dataclass(frozen=True)
class TrendTerm:
    slug: str
    brand_query: str
    label: str
    notes: str = ""


TRENDS: tuple[TrendTerm, ...] = (
    TrendTerm("camelbak_water_bottle", "camelbak", "CamelBak"),
    TrendTerm("hydro_flask_water_bottle", "hydro flask", "Hydro Flask"),
    TrendTerm("yeti_water_bottle", "yeti", "Yeti"),
    TrendTerm("frank_green_water_bottle", "frank green", "Frank Green"),
    TrendTerm("stanley_water_bottle", "stanley", "Stanley"),
    TrendTerm("owala_water_bottle", "owala", "Owala"),
)


COUNTRIES: dict[str, str] = {
    "AU": "Australia",
    "CA": "Canada",
    "IE": "Ireland",
    "NZ": "New Zealand",
    "GB": "United Kingdom",
    "US": "United States",
}


def ensure_dirs() -> None:
    for path in (RAW_DIR / COUNTRY_PANEL_NAME, PROCESSED_DIR, CHART_DIR):
        path.mkdir(parents=True, exist_ok=True)


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def raw_path(trend: TrendTerm, geo: str) -> Path:
    return RAW_DIR / COUNTRY_PANEL_NAME / f"{trend.slug}__{geo.lower()}.csv"


def baseline_term_for_geo(geo: str) -> str:
    return LOCAL_CATEGORY_TERMS.get(geo, DEFAULT_CATEGORY_TERM)


def trend_query_for_geo(trend: TrendTerm, geo: str) -> str:
    return f"{trend.brand_query} {baseline_term_for_geo(geo)}"


def batched(items: list[TrendTerm], size: int) -> Iterable[list[TrendTerm]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def collect_trends(
    trends: Iterable[TrendTerm],
    countries: dict[str, str],
    sleep_seconds: float,
    refresh: bool,
) -> None:
    pytrends = TrendReq(
        hl="en-US",
        tz=0,
        timeout=(10, 30),
        retries=2,
        backoff_factor=0.5,
    )

    trend_list = list(trends)
    for geo, country_name in countries.items():
        missing_trends = [
            trend for trend in trend_list
            if refresh or not raw_path(trend, geo).exists()
        ]
        if not missing_trends:
            print(f"skip existing country: {country_name}")
            continue

        for trend_batch in batched(missing_trends, MAX_TRENDS_PER_BATCH):
            collect_batch(pytrends, trend_batch, geo, country_name, sleep_seconds)


def collect_batch(
    pytrends: TrendReq,
    trend_batch: list[TrendTerm],
    geo: str,
    country_name: str,
    sleep_seconds: float,
) -> None:
    batch_labels = ", ".join(trend.label for trend in trend_batch)
    baseline_term = baseline_term_for_geo(geo)
    batch_terms = [trend_query_for_geo(trend, geo) for trend in trend_batch] + [baseline_term]
    print(f"collecting batch: {country_name} / {batch_labels}")
    try:
        pytrends.build_payload(
            batch_terms,
            timeframe=TIMEFRAME,
            geo=geo,
        )
        df = pytrends.interest_over_time()
    except Exception as exc:
        print(f"ERROR: {country_name} / {batch_labels}: {exc}")
        return

    if df.empty:
        print(f"empty: {country_name} / {batch_labels}")
        return

    df = df.reset_index()
    collection_mode = (
        "paired_by_country"
        if len(trend_batch) == 1
        else "batched_by_country"
    )
    for trend in trend_batch:
        trend_query = trend_query_for_geo(trend, geo)
        if trend_query not in df.columns or baseline_term not in df.columns:
            print(f"missing columns: {trend.label} / {country_name}")
            continue

        out = raw_path(trend, geo)
        trend_df = df[["date", trend_query, baseline_term]].copy()
        if "isPartial" in df.columns:
            trend_df["isPartial"] = df["isPartial"]
        else:
            trend_df["isPartial"] = False
        trend_df["trend_slug"] = trend.slug
        trend_df["trend_label"] = trend.label
        trend_df["trend_query"] = trend_query
        trend_df["baseline_term"] = baseline_term
        trend_df["country_panel"] = COUNTRY_PANEL_NAME
        trend_df["country_panel_rule"] = COUNTRY_PANEL_RULE
        trend_df["query_convention"] = QUERY_CONVENTION
        trend_df["collection_mode"] = collection_mode
        trend_df["batch_terms"] = " | ".join(batch_terms)
        trend_df["geo"] = geo
        trend_df["country"] = country_name
        trend_df.to_csv(out, index=False)
    time.sleep(sleep_seconds)


def write_coverage_report() -> pd.DataFrame:
    rows = []
    for trend in TRENDS:
        for geo, country_name in COUNTRIES.items():
            rows.append(
                {
                    "trend_slug": trend.slug,
                    "trend_label": trend.label,
                    "trend_query": trend_query_for_geo(trend, geo),
                    "baseline_term": baseline_term_for_geo(geo),
                    "geo": geo,
                    "country": country_name,
                    "raw_file_exists": raw_path(trend, geo).exists(),
                }
            )
    coverage = pd.DataFrame(rows)
    coverage.to_csv(PROCESSED_DIR / "collection_coverage.csv", index=False)
    return coverage


def load_raw_panel() -> pd.DataFrame:
    frames = []
    valid_slugs = {trend.slug for trend in TRENDS}
    valid_geos = set(COUNTRIES)
    for path in sorted((RAW_DIR / COUNTRY_PANEL_NAME).glob("*.csv")):
        df = pd.read_csv(path, parse_dates=["date"])
        if df.empty:
            continue
        if df.loc[0, "trend_slug"] not in valid_slugs or df.loc[0, "geo"] not in valid_geos:
            continue
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No raw CSV files found in {RAW_DIR / COUNTRY_PANEL_NAME}")
    return pd.concat(frames, ignore_index=True)


def build_panel() -> pd.DataFrame:
    write_coverage_report()
    df = load_raw_panel()
    df = df[df["date"] >= pd.Timestamp(ANALYSIS_START_DATE)].copy()
    trend_lookup = {term.slug: term for term in TRENDS}

    rows = []
    for _, row in df.iterrows():
        trend = trend_lookup[row["trend_slug"]]
        trend_query = row.get("trend_query", trend_query_for_geo(trend, row["geo"]))
        baseline_term = row.get("baseline_term", baseline_term_for_geo(row["geo"]))
        trend_value = float(row.get(trend_query, 0))
        baseline_value = float(row.get(baseline_term, 0))

        rows.append(
            {
                "date": row["date"],
                "trend_slug": row["trend_slug"],
                "trend_label": row["trend_label"],
                "trend_query": row["trend_query"],
                "baseline_term": baseline_term,
                "country_panel": COUNTRY_PANEL_NAME,
                "country_panel_rule": COUNTRY_PANEL_RULE,
                "query_convention": QUERY_CONVENTION,
                "analysis_transform": "3-month trailing averages for brand and local category baseline, then brand_3m/baseline_3m",
                "geo": row["geo"],
                "country": row["country"],
                "trend_index": trend_value,
                "baseline_index": baseline_value,
                "is_partial": bool(row.get("isPartial", False)),
            }
        )

    panel = pd.DataFrame(rows)
    panel = panel.sort_values(["trend_slug", "geo", "date"])
    panel["trend_index_3m"] = (
        panel.groupby(["trend_slug", "geo"])["trend_index"]
        .transform(lambda s: s.rolling(3, min_periods=1).mean())
    )
    panel["baseline_index_3m"] = (
        panel.groupby(["trend_slug", "geo"])["baseline_index"]
        .transform(lambda s: s.rolling(3, min_periods=1).mean())
    )
    panel["relative_interest"] = pd.NA
    zero_brand = panel["trend_index_3m"] == 0
    positive_baseline = panel["baseline_index_3m"] > 0
    panel.loc[zero_brand, "relative_interest"] = 0.0
    panel.loc[~zero_brand & positive_baseline, "relative_interest"] = (
        panel.loc[~zero_brand & positive_baseline, "trend_index_3m"]
        / panel.loc[~zero_brand & positive_baseline, "baseline_index_3m"]
    )
    panel["relative_interest"] = pd.to_numeric(panel["relative_interest"], errors="coerce")

    max_by_trend = panel.groupby("trend_slug")["relative_interest"].transform("max")
    panel["score_0_100"] = 100 * panel["relative_interest"] / max_by_trend
    panel.loc[max_by_trend <= 0, "score_0_100"] = pd.NA
    panel.to_csv(PROCESSED_DIR / "trends_panel.csv", index=False)
    return panel


def compute_diffusion(panel: pd.DataFrame, threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = panel.loc[
        panel["score_0_100"].notna() & (panel["score_0_100"] >= threshold)
    ].copy()

    events = (
        eligible.groupby(["trend_slug", "trend_label", "geo", "country"], as_index=False)
        .agg(first_cross_date=("date", "min"), peak_score=("score_0_100", "max"))
        .sort_values(["trend_slug", "first_cross_date", "geo"])
    )

    trend_starts = (
        events.groupby(["trend_slug", "trend_label"], as_index=False)
        .agg(start_date=("first_cross_date", "min"), countries_crossed=("geo", "nunique"))
    )
    events = events.merge(trend_starts[["trend_slug", "start_date"]], on="trend_slug")
    events["months_since_start"] = (
        (events["first_cross_date"].dt.year - events["start_date"].dt.year) * 12
        + (events["first_cross_date"].dt.month - events["start_date"].dt.month)
    )

    milestones = []
    for _, group in events.sort_values("first_cross_date").groupby(["trend_slug", "trend_label"]):
        group = group.sort_values("first_cross_date").reset_index(drop=True)
        start_date = group.loc[0, "start_date"]
        start_year = int(start_date.year)
        for n in (5, 10, 15, 20):
            if len(group) >= n:
                hit_date = group.loc[n - 1, "first_cross_date"]
                months = (hit_date.year - start_date.year) * 12 + (hit_date.month - start_date.month)
            else:
                hit_date = pd.NaT
                months = pd.NA
            milestones.append(
                {
                    "trend_slug": group.loc[0, "trend_slug"],
                    "trend_label": group.loc[0, "trend_label"],
                    "threshold": threshold,
                    "start_date": start_date,
                    "start_year": start_year,
                    "countries_eventually_crossed": len(group),
                    "milestone_countries": n,
                    "milestone_date": hit_date,
                    "months_to_milestone": months,
                }
            )

    summary = pd.DataFrame(milestones)
    events.to_csv(PROCESSED_DIR / "diffusion_events.csv", index=False)
    summary.to_csv(PROCESSED_DIR / "diffusion_summary.csv", index=False)
    return events, summary


def build_brand_month_series(panel: pd.DataFrame) -> pd.DataFrame:
    brand_month = (
        panel.loc[panel["relative_interest"].notna()]
        .groupby(["date", "trend_slug", "trend_label"], as_index=False)
        .agg(
            average_relative_interest=("relative_interest", "mean"),
            countries_available=("geo", "nunique"),
        )
    )
    brand_month.to_csv(PROCESSED_DIR / "brand_month_average_interest.csv", index=False)
    return brand_month


def build_calendar_cumulative_brand_month(brand_month: pd.DataFrame) -> pd.DataFrame:
    cumulative = brand_month.sort_values(["trend_slug", "date"]).copy()
    cumulative["cumulative_average_relative_interest"] = (
        cumulative.groupby("trend_slug")["average_relative_interest"].cumsum()
    )
    cumulative.to_csv(PROCESSED_DIR / "brand_month_cumulative_since_2010.csv", index=False)
    return cumulative


def detect_trend_starts(brand_month: pd.DataFrame) -> pd.DataFrame:
    starts = []
    for (trend_slug, trend_label), group in brand_month.groupby(["trend_slug", "trend_label"]):
        group = group.sort_values("date").reset_index(drop=True)
        peak = group["average_relative_interest"].max()
        threshold = TREND_START_ABSOLUTE_THRESHOLD
        start_date = pd.NaT
        active_months_in_window = 0
        window_average_relative_interest = pd.NA

        for i in range(0, len(group) - TREND_START_WINDOW_MONTHS + 1):
            if group.loc[i, "average_relative_interest"] < threshold:
                continue
            window = group.loc[
                i : i + TREND_START_WINDOW_MONTHS - 1,
                "average_relative_interest",
            ]
            active_months = int((window >= threshold).sum())
            if active_months >= TREND_START_REQUIRED_ACTIVE_MONTHS:
                start_date = group.loc[i, "date"]
                active_months_in_window = active_months
                window_average_relative_interest = window.mean()
                break

        starts.append(
            {
                "trend_slug": trend_slug,
                "trend_label": trend_label,
                "start_date": start_date,
                "peak_average_relative_interest": peak,
                "start_threshold": threshold,
                "start_window_months": TREND_START_WINDOW_MONTHS,
                "required_active_months": TREND_START_REQUIRED_ACTIVE_MONTHS,
                "active_months_in_window": active_months_in_window,
                "window_average_relative_interest": window_average_relative_interest,
            }
        )

    start_df = pd.DataFrame(starts)
    start_df.to_csv(PROCESSED_DIR / "trend_start_dates.csv", index=False)
    return start_df


def add_event_time(brand_month: pd.DataFrame, starts: pd.DataFrame) -> pd.DataFrame:
    event_time = brand_month.merge(
        starts[["trend_slug", "start_date"]],
        on="trend_slug",
        how="left",
    )
    event_time["months_from_start"] = (
        (event_time["date"].dt.year - event_time["start_date"].dt.year) * 12
        + (event_time["date"].dt.month - event_time["start_date"].dt.month)
    )
    event_time.to_csv(PROCESSED_DIR / "brand_month_event_time.csv", index=False)
    return event_time


def build_cumulative_event_time(event_time: pd.DataFrame) -> pd.DataFrame:
    cumulative = event_time.dropna(subset=["months_from_start"]).copy()
    cumulative = cumulative[cumulative["months_from_start"] >= -24]
    cumulative = cumulative.sort_values(["trend_slug", "months_from_start"])
    cumulative["raw_cumulative_average_relative_interest"] = (
        cumulative.groupby("trend_slug")["average_relative_interest"].cumsum()
    )
    month_zero_lookup = (
        cumulative.loc[cumulative["months_from_start"] == 0]
        .set_index("trend_slug")["raw_cumulative_average_relative_interest"]
    )
    cumulative["cumulative_average_relative_interest"] = (
        cumulative["raw_cumulative_average_relative_interest"]
        - cumulative["trend_slug"].map(month_zero_lookup)
    )
    cumulative.to_csv(PROCESSED_DIR / "brand_month_cumulative_event_time.csv", index=False)
    return cumulative


def plot_average_interest_facets_same_axes(
    brand_month: pd.DataFrame,
    starts: pd.DataFrame,
) -> None:
    if brand_month.empty:
        return

    grid = sns.relplot(
        data=brand_month,
        x="date",
        y="average_relative_interest",
        col="trend_label",
        col_wrap=2,
        kind="line",
        height=2.8,
        aspect=1.7,
        linewidth=2.0,
        color="#3366aa",
        facet_kws={"sharey": True},
    )
    grid.set_axis_labels("", "")
    grid.set_titles("{col_name}")
    start_lookup = starts.set_index("trend_label")["start_date"].to_dict()
    for ax in grid.axes.flat:
        title = ax.get_title()
        label = title.split(" = ")[-1] if " = " in title else title
        start_date = start_lookup.get(label)
        if pd.notna(start_date):
            ax.axvline(start_date, color="#cc3333", linestyle="--", linewidth=1.4, alpha=0.9)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(True, axis="y", alpha=0.22)
    grid.fig.supylabel("Avg. brand / water bottle search intensity")
    grid.fig.suptitle("Average Relative Search Interest by Brand, Shared Y-Axis", y=1.02)
    grid.fig.tight_layout()
    grid.fig.savefig(CHART_DIR / "average_normalized_interest_by_brand.png", dpi=180)
    plt.close(grid.fig)


def plot_cumulative_calendar_facets(
    cumulative_brand_month: pd.DataFrame,
    starts: pd.DataFrame,
) -> None:
    if cumulative_brand_month.empty:
        return

    grid = sns.relplot(
        data=cumulative_brand_month,
        x="date",
        y="cumulative_average_relative_interest",
        col="trend_label",
        col_wrap=2,
        kind="line",
        height=2.8,
        aspect=1.7,
        linewidth=2.0,
        color="#3366aa",
        facet_kws={"sharey": True},
    )
    grid.set_axis_labels("", "")
    grid.set_titles("{col_name}")
    start_lookup = starts.set_index("trend_label")["start_date"].to_dict()
    for ax in grid.axes.flat:
        title = ax.get_title()
        label = title.split(" = ")[-1] if " = " in title else title
        start_date = start_lookup.get(label)
        if pd.notna(start_date):
            ax.axvline(start_date, color="#cc3333", linestyle="--", linewidth=1.4, alpha=0.9)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(True, axis="y", alpha=0.22)
    grid.fig.supylabel("Cumulative avg. brand / water bottle search intensity")
    grid.fig.suptitle("Cumulative Average Relative Search Interest Since 2010", y=1.02)
    grid.fig.tight_layout()
    grid.fig.savefig(CHART_DIR / "cumulative_average_interest_since_2010_by_brand.png", dpi=180)
    plt.close(grid.fig)


def plot_average_interest_overlay(
    brand_month: pd.DataFrame,
    starts: pd.DataFrame,
) -> None:
    if brand_month.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 6))
    palette = dict(zip(
        sorted(brand_month["trend_label"].unique()),
        sns.color_palette("tab10", n_colors=brand_month["trend_label"].nunique()),
    ))
    sns.lineplot(
        data=brand_month,
        x="date",
        y="average_relative_interest",
        hue="trend_label",
        palette=palette,
        linewidth=2.0,
        ax=ax,
    )

    start_points = brand_month.merge(
        starts[["trend_slug", "start_date"]],
        on="trend_slug",
        how="inner",
    )
    start_points = start_points[start_points["date"].eq(start_points["start_date"])]
    for _, row in start_points.iterrows():
        ax.scatter(
            row["date"],
            row["average_relative_interest"],
            s=70,
            color=palette[row["trend_label"]],
            edgecolor="white",
            linewidth=1.2,
            zorder=5,
        )
        ax.axvline(
            row["date"],
            color=palette[row["trend_label"]],
            linestyle="--",
            linewidth=1.0,
            alpha=0.28,
        )

    ax.set_title("Average Relative Search Interest by Brand")
    ax.set_xlabel("")
    ax.set_ylabel("Avg. brand / water bottle search intensity")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(title="", frameon=False, ncols=2)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "average_interest_overlay_by_brand.png", dpi=180)
    plt.close(fig)


def plot_event_time_overlay(event_time: pd.DataFrame) -> None:
    usable = event_time.dropna(subset=["months_from_start"]).copy()
    if usable.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.lineplot(
        data=usable,
        x="months_from_start",
        y="average_relative_interest",
        hue="trend_label",
        linewidth=2.0,
        palette="tab10",
        ax=ax,
    )
    ax.axvline(0, color="#222222", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.set_title("Average Relative Search Interest Around Trend Start")
    ax.set_xlabel("Months before/after trend start")
    ax.set_ylabel("Avg. brand / water bottle search intensity")
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(title="", frameon=False, ncols=2)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "event_time_average_interest_by_brand.png", dpi=180)
    plt.close(fig)


def plot_cumulative_event_time(cumulative_event_time: pd.DataFrame) -> None:
    if cumulative_event_time.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.lineplot(
        data=cumulative_event_time,
        x="months_from_start",
        y="cumulative_average_relative_interest",
        hue="trend_label",
        linewidth=2.0,
        palette="tab10",
        ax=ax,
    )
    ax.set_title("Cumulative Average Relative Search Interest Since Trend Start")
    ax.set_xlabel("Months since trend start")
    ax.set_ylabel("Cumulative avg. brand / water bottle search intensity")
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(title="", frameon=False, ncols=2)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "cumulative_event_time_average_interest_by_brand.png", dpi=180)
    plt.close(fig)


def plot_average_interest_by_brand(panel: pd.DataFrame) -> None:
    brand_month = build_brand_month_series(panel)
    cumulative_brand_month = build_calendar_cumulative_brand_month(brand_month)
    starts = detect_trend_starts(brand_month)
    event_time = add_event_time(brand_month, starts)
    cumulative_event_time = build_cumulative_event_time(event_time)
    plot_average_interest_facets_same_axes(brand_month, starts)
    plot_cumulative_calendar_facets(cumulative_brand_month, starts)
    plot_average_interest_overlay(brand_month, starts)
    plot_event_time_overlay(event_time)
    plot_cumulative_event_time(cumulative_event_time)


def write_notes(summary: pd.DataFrame, threshold: float) -> None:
    lines = [
        "# Initial Findings",
        "",
        f"Threshold: country first crosses trend-normalized score >= {threshold:.0f}.",
        "",
        f"Country panel: `{COUNTRY_PANEL_NAME}` - {COUNTRY_PANEL_RULE}",
        f"Query convention: `{QUERY_CONVENTION}`. Baseline term is `drink bottle` in Australia/New Zealand and `water bottle` elsewhere.",
        "Analysis transform: 3-month trailing average of brand index divided by 3-month trailing average of the local category baseline index.",
        "",
        "## Diffusion Milestones",
        "",
        "```text",
        summary.to_string(index=False),
        "```",
        "",
        "Interpretation caveats:",
        "",
        "- Google Trends scores are sampled and normalized; rerunning can slightly change values.",
        "- The denominator uses the local English category term, so this first pass is strongest for English-search-heavy markets.",
        "- Brand queries use a consistent `{brand} {local bottle category}` convention to reduce cross-product query-composition differences.",
    ]
    (PROCESSED_DIR / "initial_findings.md").write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true", help="Collect raw Google Trends data.")
    parser.add_argument("--analyze", action="store_true", help="Build panel and diffusion outputs.")
    parser.add_argument("--charts", action="store_true", help="Create charts from processed data.")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch existing raw files.")
    parser.add_argument("--sleep", type=float, default=1.5, help="Seconds between Trends requests.")
    parser.add_argument("--threshold", type=float, default=20.0, help="Diffusion threshold on 0-100 trend score.")
    return parser.parse_args()


def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning, module="pytrends")
    args = parse_args()
    ensure_dirs()

    if args.collect:
        collect_trends(TRENDS, COUNTRIES, sleep_seconds=args.sleep, refresh=args.refresh)

    panel = None
    events = None
    summary = None

    if args.analyze:
        panel = build_panel()
        events, summary = compute_diffusion(panel, threshold=args.threshold)
        write_notes(summary, threshold=args.threshold)

    if args.charts:
        if panel is None:
            panel = pd.read_csv(PROCESSED_DIR / "trends_panel.csv", parse_dates=["date"])
        plot_average_interest_by_brand(panel)


if __name__ == "__main__":
    main()
