const COUNTRY_COLORS = {
  Australia: "#2f6f73",
  Canada: "#b44b3f",
  Ireland: "#6c8d42",
  "New Zealand": "#7c5f9e",
  "United Kingdom": "#c4892f",
  "United States": "#3c6ea8",
};

const BRAND_ORDER = ["CamelBak", "Hydro Flask", "Yeti", "Frank Green", "Stanley", "Owala"];
const CUMULATIVE_TARGET = 1;
const CUMULATIVE_X_MIN = -24;
const CUMULATIVE_X_MAX = 130;

const tooltip = document.querySelector("#tooltip");
const countryChart = document.querySelector("#countryChart");
const cumulativeChart = document.querySelector("#cumulativeChart");
const activeCountries = new Set(Object.keys(COUNTRY_COLORS));

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"' && quoted && next === '"') {
      field += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(field);
      if (row.some((value) => value.length)) rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }

  const [header, ...body] = rows;
  return body.map((values) => Object.fromEntries(header.map((key, index) => [key, values[index] ?? ""])));
}

async function loadCsv(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path}`);
  return parseCsv(await response.text());
}

function byBrand(rows) {
  return BRAND_ORDER.map((brand) => ({
    brand,
    rows: rows.filter((row) => row.trend_label === brand),
  })).filter((group) => group.rows.length);
}

function extent(values) {
  return [Math.min(...values), Math.max(...values)];
}

function makeScale(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

function makeSvg(width, height) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  return svg;
}

function el(name, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function textNode(value, x, y, className, anchor = "start") {
  const node = el("text", { x, y, class: className, "text-anchor": anchor });
  node.textContent = value;
  return node;
}

function labeledText(parent, value, x, y, className, anchor = "middle") {
  const text = textNode(value, x, y, className, anchor);
  parent.appendChild(text);
  const box = text.getBBox();
  const padX = 5;
  const padY = 3;
  const bg = el("rect", {
    x: box.x - padX,
    y: box.y - padY,
    width: box.width + padX * 2,
    height: box.height + padY * 2,
    class: "label-bg",
  });
  parent.insertBefore(bg, text);
  return text;
}

function pathFrom(rows, xScale, yScale, xKey, yKey) {
  return rows
    .map((row, index) => `${index === 0 ? "M" : "L"}${xScale(row[xKey]).toFixed(2)},${yScale(row[yKey]).toFixed(2)}`)
    .join(" ");
}

function showTooltip(event, title, lines) {
  tooltip.innerHTML = `<strong>${title}</strong>${lines.join("<br>")}`;
  tooltip.style.left = `${event.clientX}px`;
  tooltip.style.top = `${event.clientY}px`;
  tooltip.classList.add("is-visible");
}

function hideTooltip() {
  tooltip.classList.remove("is-visible");
}

function monthLabel(date) {
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function longMonthLabel(dateText) {
  return new Date(dateText).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function formatAxisNumber(value) {
  if (Math.abs(value) < 0.001) return "0";
  return value.toFixed(value % 1 ? 1 : 0);
}

function nearestPoint(series, event, svg, gx, gy, xScale, xKey) {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const svgPoint = point.matrixTransform(svg.getScreenCTM().inverse());
  const localX = svgPoint.x - gx;
  return series.reduce((best, row) => {
    const distance = Math.abs(xScale(row[xKey]) - localX);
    return distance < best.distance ? { ...row, distance } : best;
  }, { ...series[0], distance: Infinity });
}

function makeArrowDef(svg) {
  const defs = el("defs");
  const marker = el("marker", {
    id: "arrowhead",
    markerWidth: 8,
    markerHeight: 8,
    refX: 7,
    refY: 4,
    orient: "auto",
  });
  marker.appendChild(el("path", { d: "M0,0 L8,4 L0,8 Z", fill: "#d14f3f" }));
  defs.appendChild(marker);
  svg.appendChild(defs);
}

function renderCountryChart(panelRows, starts) {
  countryChart.textContent = "";

  const rows = panelRows
    .filter((row) => BRAND_ORDER.includes(row.trend_label) && activeCountries.has(row.country))
    .map((row) => ({
      ...row,
      dateValue: new Date(row.date).getTime(),
      relative_interest: Number(row.relative_interest || 0),
    }));

  const groups = byBrand(rows);
  if (!groups.length) return;

  const width = 1180;
  const margin = { top: 38, right: 36, bottom: 52, left: 72 };
  const facetGapX = 52;
  const facetGapY = 72;
  const cols = 2;
  const rowsOfFacets = Math.ceil(groups.length / cols);
  const facetWidth = (width - margin.left - margin.right - facetGapX) / cols;
  const facetHeight = 210;
  const height = margin.top + margin.bottom + rowsOfFacets * facetHeight + (rowsOfFacets - 1) * facetGapY;
  const allDates = rows.map((row) => row.dateValue);
  const maxY = Math.max(0.05, ...rows.map((row) => row.relative_interest));
  const yMax = Math.ceil(maxY / 0.05) * 0.05;
  const xScale = makeScale(extent(allDates), [0, facetWidth]);
  const yScale = makeScale([0, yMax], [facetHeight, 0]);
  const svg = makeSvg(width, height);

  const axisTitle = textNode("Relative search interest = brand-specific interest as share of market", 18, margin.top + (height - margin.top - margin.bottom) / 2, "axis-title", "middle");
  axisTitle.setAttribute("transform", `rotate(-90 18 ${margin.top + (height - margin.top - margin.bottom) / 2})`);
  svg.appendChild(axisTitle);
  svg.appendChild(textNode("Month", width / 2, height - 12, "axis-title", "middle"));

  const startByBrand = new Map(starts.map((row) => [row.trend_label, new Date(row.start_date).getTime()]));
  const yearTicks = [2010, 2014, 2018, 2022, 2026].map((year) => new Date(`${year}-01-01`).getTime());
  const yTicks = Array.from({ length: Math.floor(yMax / 0.05) + 1 }, (_, index) => index * 0.05);

  groups.forEach((group, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const gx = margin.left + col * (facetWidth + facetGapX);
    const gy = margin.top + row * (facetHeight + facetGapY);
    const facet = el("g", { transform: `translate(${gx},${gy})` });
    svg.appendChild(facet);

    facet.appendChild(textNode(group.brand, 0, -16, "facet-title"));

    yTicks.forEach((tick) => {
      const y = yScale(tick);
      facet.appendChild(el("line", { x1: 0, x2: facetWidth, y1: y, y2: y, class: "grid-line" }));
      facet.appendChild(textNode(tick.toFixed(2), -10, y + 4, "axis-label", "end"));
    });

    yearTicks.forEach((tick) => {
      const x = xScale(tick);
      facet.appendChild(el("line", { x1: x, x2: x, y1: facetHeight, y2: facetHeight + 5, class: "axis-line" }));
      facet.appendChild(textNode(new Date(tick).getFullYear(), x, facetHeight + 22, "axis-label", "middle"));
    });

    const startDate = startByBrand.get(group.brand);
    if (Number.isFinite(startDate)) {
      const x = xScale(startDate);
      facet.appendChild(el("line", { x1: x, x2: x, y1: 0, y2: facetHeight, class: "takeoff-line" }));
      facet.appendChild(textNode("Brand takeoff", Math.min(x + 6, facetWidth - 92), 12, "annotation"));
    }

    Object.keys(COUNTRY_COLORS).forEach((country) => {
      if (!activeCountries.has(country)) return;
      const series = group.rows
        .filter((item) => item.country === country)
        .sort((a, b) => a.dateValue - b.dateValue);
      if (series.length < 2) return;
      const path = el("path", {
        d: pathFrom(series, xScale, yScale, "dateValue", "relative_interest"),
        class: "series-line",
        stroke: COUNTRY_COLORS[country],
        opacity: 0.9,
      });
      path.addEventListener("mousemove", (event) => {
        const nearest = nearestPoint(series, event, path.ownerSVGElement, gx, gy, xScale, "dateValue");
        showTooltip(event, `${group.brand} in ${country}`, [
          monthLabel(new Date(nearest.dateValue)),
          `Relative interest: ${nearest.relative_interest.toFixed(4)}`,
        ]);
      });
      path.addEventListener("mouseleave", hideTooltip);
      facet.appendChild(path);
    });

    facet.appendChild(el("line", { x1: 0, x2: facetWidth, y1: facetHeight, y2: facetHeight, class: "axis-line" }));
    facet.appendChild(el("line", { x1: 0, x2: 0, y1: 0, y2: facetHeight, class: "axis-line" }));
  });

  countryChart.appendChild(svg);
}

function renderCumulativeChart(cumulativeRows, starts) {
  cumulativeChart.textContent = "";

  const rows = cumulativeRows
    .filter((row) => BRAND_ORDER.includes(row.trend_label))
    .map((row) => ({
      ...row,
      months_from_start: Number(row.months_from_start),
      cumulative_average_relative_interest: Number(row.cumulative_average_relative_interest || 0),
    }));

  const groups = byBrand(rows);
  if (!groups.length) return;

  const width = 1180;
  const margin = { top: 38, right: 36, bottom: 58, left: 76 };
  const facetGapX = 52;
  const facetGapY = 72;
  const cols = 2;
  const rowsOfFacets = Math.ceil(groups.length / cols);
  const facetWidth = (width - margin.left - margin.right - facetGapX) / cols;
  const facetHeight = 210;
  const height = margin.top + margin.bottom + rowsOfFacets * facetHeight + (rowsOfFacets - 1) * facetGapY;
  const minMonth = CUMULATIVE_X_MIN;
  const maxMonth = CUMULATIVE_X_MAX;
  const minY = Math.min(-0.15, ...rows.map((row) => row.cumulative_average_relative_interest));
  const maxY = Math.max(1.2, ...rows.map((row) => row.cumulative_average_relative_interest));
  const yMin = Math.floor(minY / 0.25) * 0.25;
  const yMax = Math.ceil(maxY / 0.5) * 0.5;
  const xScale = makeScale([minMonth, maxMonth], [0, facetWidth]);
  const yScale = makeScale([yMin, yMax], [facetHeight, 0]);
  const svg = makeSvg(width, height);
  makeArrowDef(svg);
  const axisTitle = textNode("Change in cumulative relative search interest (Month 0 = 0)", 18, margin.top + (height - margin.top - margin.bottom) / 2, "axis-title", "middle");
  axisTitle.setAttribute("transform", `rotate(-90 18 ${margin.top + (height - margin.top - margin.bottom) / 2})`);
  svg.appendChild(axisTitle);
  svg.appendChild(textNode("Months since brand takeoff", width / 2, height - 12, "axis-title", "middle"));

  const startByBrand = new Map(starts.map((row) => [row.trend_label, row.start_date]));
  const xTicks = [];
  for (let tick = Math.ceil(minMonth / 24) * 24; tick <= maxMonth; tick += 24) {
    xTicks.push(tick);
  };
  const yTicks = [0];
  for (let tick = 0.5; tick <= yMax + 0.001; tick += 0.5) yTicks.push(tick);

  groups.forEach((group, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const gx = margin.left + col * (facetWidth + facetGapX);
    const gy = margin.top + row * (facetHeight + facetGapY);
    const facet = el("g", { transform: `translate(${gx},${gy})` });
    svg.appendChild(facet);

    const series = group.rows
      .filter((item) => item.months_from_start >= minMonth && item.months_from_start <= maxMonth)
      .sort((a, b) => a.months_from_start - b.months_from_start);
    facet.appendChild(textNode(`${group.brand} (${longMonthLabel(startByBrand.get(group.brand))})`, 0, -16, "facet-title"));

    yTicks.forEach((tick) => {
      const y = yScale(tick);
      facet.appendChild(el("line", { x1: 0, x2: facetWidth, y1: y, y2: y, class: "grid-line" }));
      facet.appendChild(textNode(formatAxisNumber(tick), -10, y + 4, "axis-label", "end"));
    });

    xTicks.forEach((tick) => {
      if (tick < minMonth || tick > maxMonth) return;
      const x = xScale(tick);
      facet.appendChild(el("line", { x1: x, x2: x, y1: facetHeight, y2: facetHeight + 5, class: "axis-line" }));
      facet.appendChild(textNode(String(tick), x, facetHeight + 22, "axis-label", "middle"));
    });

    facet.appendChild(el("line", {
      x1: xScale(0),
      x2: xScale(0),
      y1: 0,
      y2: facetHeight,
      class: "takeoff-line",
    }));
    facet.appendChild(el("line", {
      x1: 0,
      x2: facetWidth,
      y1: yScale(0),
      y2: yScale(0),
      class: "axis-line",
    }));
    facet.appendChild(el("line", {
      x1: 0,
      x2: facetWidth,
      y1: yScale(CUMULATIVE_TARGET),
      y2: yScale(CUMULATIVE_TARGET),
      class: "target-line",
    }));

    const path = el("path", {
      d: pathFrom(series, xScale, yScale, "months_from_start", "cumulative_average_relative_interest"),
      class: "series-line",
      stroke: "#2f6f73",
      opacity: 0.95,
    });
    path.addEventListener("mousemove", (event) => {
      const nearest = nearestPoint(series, event, path.ownerSVGElement, gx, gy, xScale, "months_from_start");
      showTooltip(event, group.brand, [
        `${nearest.months_from_start} months from takeoff`,
        `Cumulative index: ${nearest.cumulative_average_relative_interest.toFixed(3)}`,
      ]);
    });
    path.addEventListener("mouseleave", hideTooltip);
    facet.appendChild(path);

    const hit = series.find((item) => (
      item.months_from_start >= 0
      && item.cumulative_average_relative_interest >= CUMULATIVE_TARGET
    ));
    if (hit) {
      const x = xScale(hit.months_from_start);
      const arrowY = yScale(CUMULATIVE_TARGET);
      const labelX = xScale(0) + (x - xScale(0)) / 2;
      const labelY = arrowY - 9;
      facet.appendChild(el("line", {
        x1: xScale(0),
        x2: x,
        y1: arrowY,
        y2: arrowY,
        class: "arrow-line",
      }));
      labeledText(facet, `${hit.months_from_start} months`, labelX, labelY, "annotation");
    }

    facet.appendChild(el("line", { x1: 0, x2: facetWidth, y1: facetHeight, y2: facetHeight, class: "axis-line" }));
    facet.appendChild(el("line", { x1: 0, x2: 0, y1: 0, y2: facetHeight, class: "axis-line" }));
  });

  cumulativeChart.appendChild(svg);
}

function wireCountryControls(data) {
  document.querySelectorAll(".country-toggle").forEach((button) => {
    button.style.setProperty("--country-color", COUNTRY_COLORS[button.dataset.country]);
    button.addEventListener("click", () => {
      const country = button.dataset.country;
      if (activeCountries.has(country)) {
        activeCountries.delete(country);
        button.classList.remove("is-active");
      } else {
        activeCountries.add(country);
        button.classList.add("is-active");
      }
      renderCountryChart(data.panelRows, data.starts);
    });
  });
}

function setupReveal() {
  const revealItems = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      entry.target.classList.toggle("is-visible", entry.isIntersecting);
    });
  }, { rootMargin: "0px 0px -12% 0px", threshold: 0.12 });
  revealItems.forEach((item) => observer.observe(item));
}

async function init() {
  setupReveal();
  try {
    const [panelRows, starts, cumulativeRows] = await Promise.all([
      loadCsv("data/processed/trends_panel.csv"),
      loadCsv("data/processed/trend_start_dates.csv"),
      loadCsv("data/processed/brand_month_cumulative_event_time.csv"),
    ]);
    const data = { panelRows, starts, cumulativeRows };
    wireCountryControls(data);
    renderCountryChart(panelRows, starts);
    renderCumulativeChart(cumulativeRows, starts);
  } catch (error) {
    countryChart.textContent = "Could not load chart data.";
    cumulativeChart.textContent = "Could not load chart data.";
    console.error(error);
  }
}

init();
