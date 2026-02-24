"""
Generates a self-contained interactive HTML dashboard report from analysis results.
Uses Chart.js (CDN) for charts. No external CSS frameworks.
"""

from datetime import datetime, timezone
from html import escape


def _short_catalog_name(uri: str) -> str:
    """Extract a readable short name from a catalog URI."""
    parts = uri.rstrip("/").split("/")
    for part in reversed(parts):
        if part and len(part) > 2:
            return part
    return uri[:40]


def _compliance_pct(data: dict) -> float:
    total = data.get("total_entities", 0)
    if total == 0:
        return 0.0
    return round(data.get("entities_with_property", 0) / total * 100, 1)


def _cell_color(pct: float, req: str) -> str:
    if req == "M":
        if pct >= 90:
            return "#d4edda"
        elif pct >= 50:
            return "#fff3cd"
        else:
            return "#f8d7da"
    elif req == "R":
        if pct >= 70:
            return "#d4edda"
        elif pct >= 30:
            return "#fff3cd"
        else:
            return "#f8d7da"
    else:
        if pct >= 50:
            return "#d4edda"
        else:
            return "#f0f0f0"


def _vocab_badge(vocab_type: str) -> str:
    colors = {"C": "#0d6efd", "V": "#6f42c1", "F": "#6c757d"}
    labels = {"C": "Codelist", "V": "Controlled", "F": "Free text"}
    color = colors.get(vocab_type, "#6c757d")
    label = labels.get(vocab_type, vocab_type)
    return f'<span style="background:{color};color:#fff;padding:2px 6px;border-radius:3px;font-size:0.75em">{label}</span>'


def generate_report(
    path: str,
    source_url: str,
    endpoint_type: str,
    property_results: dict,
    vocabulary_results: dict,
) -> None:
    """Write the full HTML report to the given file path."""

    catalog_uris = property_results.get("catalog_uris", [])
    catalog_labels = {uri: _short_catalog_name(uri) for uri in catalog_uris}
    num_catalogs = len(catalog_uris)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- Build property compliance table HTML ---
    prop_table_html = _build_property_table(property_results, catalog_uris, catalog_labels)

    # --- Build vocabulary table HTML ---
    vocab_table_html = _build_vocabulary_table(vocabulary_results, catalog_uris, catalog_labels)

    # --- Chart data ---
    bar_chart_data = _build_compliance_chart_data(property_results, catalog_uris, catalog_labels)
    vocab_pie_data = _build_vocab_pie_data(vocabulary_results, catalog_uris)
    radar_data = _build_radar_data(property_results, catalog_uris, catalog_labels)

    # --- Dataset/distribution counts ---
    stat_cards = _build_stat_cards(property_results, catalog_uris)

    endpoint_type_label = {
        "ldes": "LDES (Linked Data Event Stream)",
        "hydra": "Hydra Collection",
        "ckan": "CKAN DCAT API",
        "dcat": "DCAT Feed",
    }.get(endpoint_type, endpoint_type)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MobilityDCAT-AP Validation Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --red: #E32119;
    --red-dark: #b51a13;
    --grey: #f4f4f4;
    --border: #dee2e6;
    --text: #212529;
    --muted: #6c757d;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: #fff; }}
  header {{ background: var(--red); color: #fff; padding: 1.5rem 2rem; }}
  header h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }}
  header .subtitle {{ opacity: 0.85; font-size: 0.9rem; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.8em; background:rgba(255,255,255,0.2); border:1px solid rgba(255,255,255,0.4); margin-left:0.5rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem 2rem; }}
  .meta {{ background: var(--grey); border-radius: 6px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; font-size: 0.88rem; color: var(--muted); }}
  .meta strong {{ color: var(--text); }}
  .stat-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .stat-card {{ background: var(--grey); border-radius: 8px; padding: 1rem 1.25rem; text-align: center; }}
  .stat-card .number {{ font-size: 2rem; font-weight: 700; color: var(--red); }}
  .stat-card .label {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }}
  h2 {{ font-size: 1.15rem; font-weight: 600; margin: 2rem 0 1rem; padding-bottom: 0.4rem; border-bottom: 2px solid var(--red); }}
  h3 {{ font-size: 0.95rem; font-weight: 600; margin: 1.5rem 0 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
  .table-wrap {{ overflow-x: auto; margin-bottom: 1.5rem; border: 1px solid var(--border); border-radius: 6px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.82rem; }}
  th {{ background: #343a40; color: #fff; padding: 0.5rem 0.75rem; text-align: left; font-weight: 600; white-space: nowrap; }}
  td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  .req-badge {{ display:inline-block; width:20px; height:20px; line-height:20px; text-align:center; border-radius:50%; font-size:0.7em; font-weight:700; color:#fff; margin-right:4px; }}
  .req-M {{ background:#dc3545; }}
  .req-R {{ background:#fd7e14; }}
  .req-O {{ background:#6c757d; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  @media (max-width: 800px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
  .chart-box {{ border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }}
  .chart-box h3 {{ margin-top: 0; }}
  canvas {{ max-height: 320px; }}
  .legend {{ font-size: 0.8rem; color: var(--muted); margin-top: 1rem; }}
  .legend span {{ display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:4px; vertical-align:middle; }}
  footer {{ margin-top: 3rem; padding: 1.5rem 2rem; background: var(--grey); border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--muted); text-align: center; }}
  footer a {{ color: var(--red); text-decoration: none; }}
</style>
</head>
<body>

<header>
  <h1>MobilityDCAT-AP Validation Report
    <span class="badge">{escape(endpoint_type_label)}</span>
  </h1>
  <div class="subtitle">{escape(source_url)}</div>
</header>

<div class="container">

  <div class="meta">
    <strong>Generated:</strong> {generated_at} &nbsp;|&nbsp;
    <strong>Endpoint type:</strong> {escape(endpoint_type_label)} &nbsp;|&nbsp;
    <strong>Catalogs found:</strong> {num_catalogs}
  </div>

  {stat_cards}

  <h2>Property Compliance</h2>
  <div class="chart-row">
    <div class="chart-box">
      <h3>Mandatory Property Coverage per Catalog</h3>
      <canvas id="barChart"></canvas>
    </div>
    <div class="chart-box">
      <h3>Coverage by Requirement Level</h3>
      <canvas id="radarChart"></canvas>
    </div>
  </div>

  {prop_table_html}

  <div class="legend">
    <span style="background:#d4edda"></span> Good (&ge;90% mandatory, &ge;70% recommended)
    <span style="background:#fff3cd;margin-left:8px"></span> Partial
    <span style="background:#f8d7da;margin-left:8px"></span> Poor
    &nbsp;&nbsp;
    <span class="req-badge req-M">M</span> Mandatory
    <span class="req-badge req-R">R</span> Recommended
    <span class="req-badge req-O">O</span> Optional
  </div>

  <h2>Controlled Vocabulary Analysis</h2>
  <div class="chart-row">
    <div class="chart-box">
      <h3>Vocabulary Type Distribution</h3>
      <canvas id="vocabPieChart"></canvas>
    </div>
    <div class="chart-box" style="align-self:start">
      <h3>Legend</h3>
      <p style="font-size:0.85rem;line-height:1.8">
        {_vocab_badge("C")} <strong>Codelist</strong> – URI-based controlled vocabulary (≤5 unique values or &gt;50% URI values)<br>
        {_vocab_badge("V")} <strong>Controlled</strong> – Limited vocabulary (top 5 values &gt;80% of usage)<br>
        {_vocab_badge("F")} <strong>Free text</strong> – Unconstrained values
      </p>
    </div>
  </div>

  {vocab_table_html}

</div>

<footer>
  Generated by <a href="https://redpencil.io" target="_blank">redpencil.io</a> MobilityDCAT-AP Validator &nbsp;|&nbsp;
  Specification: <a href="https://mobilitydcat-ap.github.io/mobilityDCAT-AP/" target="_blank">MobilityDCAT-AP</a>
</footer>

<script>
// Bar chart: mandatory compliance per catalog
const barCtx = document.getElementById('barChart').getContext('2d');
new Chart(barCtx, {{
  type: 'bar',
  data: {bar_chart_data},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{
      y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: '% with property' }} }}
    }}
  }}
}});

// Radar chart: M/R/O coverage per catalog
const radarCtx = document.getElementById('radarChart').getContext('2d');
new Chart(radarCtx, {{
  type: 'radar',
  data: {radar_data},
  options: {{
    responsive: true,
    scales: {{ r: {{ beginAtZero: true, max: 100 }} }},
    plugins: {{ legend: {{ position: 'top' }} }}
  }}
}});

// Vocab pie chart
const pieCtx = document.getElementById('vocabPieChart').getContext('2d');
new Chart(pieCtx, {{
  type: 'doughnut',
  data: {vocab_pie_data},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'right' }} }}
  }}
}});
</script>

</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_stat_cards(property_results: dict, catalog_uris: list) -> str:
    """Build summary stat cards from property analysis results."""
    classes = property_results.get("classes", {})
    num_catalogs = len(catalog_uris)

    # Approximate dataset/distribution counts from analysis data
    num_datasets = 0
    num_distributions = 0
    ds_class = classes.get("dcat:Dataset", {})
    dist_class = classes.get("dcat:Distribution", {})

    for prop_data in (ds_class.get("mandatory") or []):
        for catalog_uri in catalog_uris:
            total = prop_data["per_catalog"].get(catalog_uri, {}).get("total_entities", 0)
            if total > num_datasets:
                num_datasets = total
        break  # Just use first mandatory property total as proxy

    for prop_data in (dist_class.get("mandatory") or []):
        for catalog_uri in catalog_uris:
            total = prop_data["per_catalog"].get(catalog_uri, {}).get("total_entities", 0)
            if total > num_distributions:
                num_distributions = total
        break

    cards = [
        (num_catalogs, "Catalogs"),
        (num_datasets, "Datasets (est.)"),
        (num_distributions, "Distributions (est.)"),
    ]
    html = '<div class="stat-cards">'
    for number, label in cards:
        html += f'<div class="stat-card"><div class="number">{number}</div><div class="label">{label}</div></div>'
    html += "</div>"
    return html


def _build_property_table(property_results: dict, catalog_uris: list, catalog_labels: dict) -> str:
    classes = property_results.get("classes", {})

    html = ""
    for class_name, class_data in classes.items():
        html += f"<h3>{escape(class_name)}</h3>"
        html += '<div class="table-wrap"><table>'

        # Header
        html += "<tr><th>Property</th>"
        for uri in catalog_uris:
            html += f"<th>{escape(catalog_labels[uri])}</th>"
        html += "</tr>"

        for req_level in ("mandatory", "recommended", "optional"):
            req_char = req_level[0].upper()
            for prop in class_data.get(req_level, []):
                html += "<tr>"
                html += (
                    f'<td><span class="req-badge req-{req_char}">{req_char}</span>'
                    f'{escape(prop["short_name"])}</td>'
                )
                for uri in catalog_uris:
                    data = prop["per_catalog"].get(uri, {})
                    pct = _compliance_pct(data)
                    total = data.get("total_entities", 0)
                    with_prop = data.get("entities_with_property", 0)
                    color = _cell_color(pct, req_char)
                    if total == 0:
                        cell = "<em style='color:#aaa'>N/A</em>"
                    else:
                        cell = f"{with_prop}/{total} <small>({pct:.0f}%)</small>"
                    html += f'<td style="background:{color}">{cell}</td>'
                html += "</tr>"

        html += "</table></div>"
    return html


def _build_vocabulary_table(vocabulary_results: dict, catalog_uris: list, catalog_labels: dict) -> str:
    entity_types = vocabulary_results.get("entity_types", {})

    html = ""
    for entity_type, props in entity_types.items():
        if not props:
            continue
        html += f"<h3>{escape(entity_type.replace('s', ' ').title())} vocabulary</h3>"
        html += '<div class="table-wrap"><table>'

        html += "<tr><th>Property</th>"
        for uri in catalog_uris:
            html += f"<th>{escape(catalog_labels[uri])}</th>"
        html += "</tr>"

        for prop in props:
            html += f"<tr><td>{escape(prop['short_name'])}</td>"
            for uri in catalog_uris:
                data = prop["per_catalog"].get(uri, {})
                total = data.get("total_entities", 0)
                with_prop = data.get("entities_with_property", 0)
                vocab_type = data.get("vocab_type", "F")
                unique = data.get("unique_values", 0)
                if total == 0:
                    html += "<td><em style='color:#aaa'>N/A</em></td>"
                elif with_prop == 0:
                    html += "<td>0%</td>"
                else:
                    pct = round(with_prop / total * 100)
                    badge = _vocab_badge(vocab_type)
                    html += f"<td>{pct}% {badge} <small>{unique} vals</small></td>"
            html += "</tr>"

        html += "</table></div>"
    return html


def _build_compliance_chart_data(property_results: dict, catalog_uris: list, catalog_labels: dict) -> str:
    """Build Chart.js bar chart data for mandatory property compliance per catalog."""
    import json

    labels = [catalog_labels[u] for u in catalog_uris]
    classes = property_results.get("classes", {})

    datasets = []
    colors = ["#E32119", "#3a86ff", "#06d6a0", "#ffbe0b", "#fb5607"]

    for i, (class_name, class_data) in enumerate(classes.items()):
        mandatory_props = class_data.get("mandatory", [])
        if not mandatory_props:
            continue
        data_points = []
        for uri in catalog_uris:
            totals = [p["per_catalog"].get(uri, {}).get("total_entities", 0) for p in mandatory_props]
            with_props = [p["per_catalog"].get(uri, {}).get("entities_with_property", 0) for p in mandatory_props]
            total_sum = sum(totals)
            with_sum = sum(with_props)
            pct = round(with_sum / total_sum * 100, 1) if total_sum > 0 else 0
            data_points.append(pct)

        datasets.append({
            "label": class_name,
            "data": data_points,
            "backgroundColor": colors[i % len(colors)] + "cc",
            "borderColor": colors[i % len(colors)],
            "borderWidth": 1,
        })

    return json.dumps({"labels": labels, "datasets": datasets})


def _build_radar_data(property_results: dict, catalog_uris: list, catalog_labels: dict) -> str:
    import json

    classes = property_results.get("classes", {})
    radar_labels = ["Mandatory", "Recommended", "Optional"]
    colors = ["rgba(227,33,25,0.4)", "rgba(58,134,255,0.4)", "rgba(6,214,160,0.4)", "rgba(255,190,11,0.4)"]
    border_colors = ["#E32119", "#3a86ff", "#06d6a0", "#ffbe0b"]

    datasets = []
    for i, uri in enumerate(catalog_uris):
        label = catalog_labels[uri]
        data_points = []
        for req_level in ("mandatory", "recommended", "optional"):
            total_sum = 0
            with_sum = 0
            for class_data in classes.values():
                for prop in class_data.get(req_level, []):
                    d = prop["per_catalog"].get(uri, {})
                    total_sum += d.get("total_entities", 0)
                    with_sum += d.get("entities_with_property", 0)
            pct = round(with_sum / total_sum * 100, 1) if total_sum > 0 else 0
            data_points.append(pct)

        datasets.append({
            "label": label,
            "data": data_points,
            "fill": True,
            "backgroundColor": colors[i % len(colors)],
            "borderColor": border_colors[i % len(border_colors)],
            "pointBackgroundColor": border_colors[i % len(border_colors)],
        })

    return json.dumps({"labels": radar_labels, "datasets": datasets})


def _build_vocab_pie_data(vocabulary_results: dict, catalog_uris: list) -> str:
    import json

    counts = {"C": 0, "V": 0, "F": 0}
    for entity_type, props in vocabulary_results.get("entity_types", {}).items():
        for prop in props:
            for uri in catalog_uris:
                data = prop["per_catalog"].get(uri, {})
                if data.get("entities_with_property", 0) > 0:
                    vt = data.get("vocab_type", "F")
                    counts[vt] = counts.get(vt, 0) + 1

    return json.dumps({
        "labels": ["Codelist (C)", "Controlled (V)", "Free text (F)"],
        "datasets": [{
            "data": [counts["C"], counts["V"], counts["F"]],
            "backgroundColor": ["#0d6efd", "#6f42c1", "#6c757d"],
        }]
    })
