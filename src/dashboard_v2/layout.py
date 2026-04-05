"""Page shell: CSS, D3 CDN, shared rendering JS, nav bar."""

from . import colors as C


def css():
    """Return the complete stylesheet."""
    return f"""
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        background: {C.BG};
        color: {C.TEXT};
        line-height: 1.5;
        padding: 0;
    }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 16px 20px; }}

    /* Nav */
    .nav {{ display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid {C.BORDER}; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }}
    .nav a {{
        color: {C.TEXT_MUTED}; text-decoration: none; font-size: 13px; font-weight: 500;
        padding: 4px 10px; border-radius: 6px; transition: all 0.15s;
    }}
    .nav a:hover {{ color: {C.TEXT}; background: {C.SURFACE}; }}
    .nav a.active {{ color: {C.TEXT}; background: {C.SURFACE}; font-weight: 600; }}

    /* Header */
    .header {{ margin-bottom: 24px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
    .badge {{
        font-size: 11px; font-weight: 700; letter-spacing: 1px;
        padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
    }}
    .badge-live {{ background: rgba(240,136,62,0.15); color: #f0883e; border: 1px solid rgba(240,136,62,0.3); }}
    .badge-paper {{ background: rgba(88,166,255,0.12); color: #58a6ff; border: 1px solid rgba(88,166,255,0.2); }}
    .header-meta {{ font-size: 12px; color: {C.TEXT_DIM}; margin-top: 4px; }}

    /* Section */
    .section {{
        background: {C.SURFACE}; border: 1px solid {C.BORDER_LIGHT};
        border-radius: 10px; padding: 20px; margin-bottom: 20px;
    }}
    .section-live {{ border-left: 3px solid {C.LIVE["accent"]}; }}
    .section-paper {{ border-left: 3px solid {C.PAPER["accent"]}; }}
    .section-title {{
        font-size: 12px; font-weight: 700; color: {C.NEUTRAL};
        letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 14px;
    }}

    /* Hero number */
    .hero {{ font-size: 36px; font-weight: 800; margin: 4px 0 8px; }}
    .hero-positive {{ color: {C.PROFIT}; }}
    .hero-negative {{ color: {C.LOSS}; }}
    .hero-zero {{ color: {C.NEUTRAL}; }}

    /* Metrics row */
    .metrics {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 14px; }}
    .metric {{
        flex: 1 1 120px; background: {C.BG}; border-radius: 8px;
        padding: 10px 14px; min-width: 120px;
    }}
    .metric-label {{ font-size: 11px; color: {C.TEXT_DIM}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
    .metric-value {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}

    /* Provenance */
    .provenance {{ font-size: 11px; color: {C.TEXT_MUTED}; margin-top: 8px; }}
    .provenance-tag {{
        background: {C.BORDER}; padding: 1px 6px; border-radius: 3px;
        margin-right: 6px; font-size: 10px;
    }}

    /* Chart container */
    .chart-container {{ margin: 16px 0 8px; }}
    .chart-container svg {{ width: 100%; height: auto; display: block; }}
    .chart-empty {{ color: {C.TEXT_MUTED}; font-size: 13px; padding: 20px 0; text-align: center; }}

    /* Conviction table */
    .conv-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .conv-table th {{
        text-align: left; padding: 8px 12px; border-bottom: 1px solid {C.BORDER};
        color: {C.NEUTRAL}; font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .conv-table td {{ padding: 8px 12px; border-bottom: 1px solid {C.BORDER}; }}

    /* Breakers */
    .breaker-row {{ display: flex; flex-wrap: wrap; gap: 20px; font-size: 13px; }}
    .breaker-item {{ display: flex; align-items: center; gap: 6px; }}
    .loss-bar {{
        width: 80px; height: 8px; background: {C.BORDER};
        border-radius: 4px; overflow: hidden; display: inline-block;
    }}
    .loss-bar-fill {{ height: 100%; border-radius: 4px; }}

    /* D3 tooltip */
    .d3-tooltip {{
        position: absolute; background: #1c2128; border: 1px solid {C.BORDER_LIGHT};
        border-radius: 6px; padding: 6px 10px; font-size: 12px; color: {C.TEXT};
        pointer-events: none; opacity: 0; transition: opacity 0.15s;
        z-index: 100;
    }}

    /* Footer */
    .footer {{ font-size: 11px; color: {C.TEXT_MUTED}; text-align: center; padding: 16px 0; }}

    /* Responsive */
    @media (max-width: 600px) {{
        .container {{ padding: 10px 12px; }}
        .hero {{ font-size: 28px; }}
        .metrics {{ gap: 8px; }}
        .metric {{ min-width: 100px; padding: 8px 10px; }}
        .metric-value {{ font-size: 15px; }}
    }}
"""


def d3_script():
    """Return the shared D3.js rendering code."""
    return """
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
(function() {
  const C = {
    bg: '#161b22', grid: '#21262d', zero: '#484f58',
    green: '#3fb950', red: '#f44336', line: '#58a6ff',
    text: '#8b949e', textLight: '#c9d1d9'
  };

  function renderCumulativePnl(el, data) {
    if (!data || data.length < 2) {
      el.innerHTML = '<div class="chart-empty">Not enough data for chart.</div>';
      return;
    }
    const margin = {top: 16, right: 16, bottom: 32, left: 56};
    const width = el.clientWidth || 860;
    const height = 260;
    const iw = width - margin.left - margin.right;
    const ih = height - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const parseDate = d => new Date(d);
    const x = d3.scaleTime()
      .domain(d3.extent(data, d => parseDate(d.date)))
      .range([0, iw]);
    const yMin = Math.min(d3.min(data, d => d.value), 0);
    const yMax = Math.max(d3.max(data, d => d.value), 0);
    const yPad = (yMax - yMin) * 0.1 || 10;
    const y = d3.scaleLinear()
      .domain([yMin - yPad, yMax + yPad])
      .range([ih, 0]);

    // Grid
    g.append('g').selectAll('line')
      .data(y.ticks(5)).enter().append('line')
      .attr('x1', 0).attr('x2', iw)
      .attr('y1', d => y(d)).attr('y2', d => y(d))
      .attr('stroke', C.grid).attr('stroke-width', 0.5);

    // Zero line
    g.append('line')
      .attr('x1', 0).attr('x2', iw)
      .attr('y1', y(0)).attr('y2', y(0))
      .attr('stroke', C.zero).attr('stroke-width', 1)
      .attr('stroke-dasharray', '6,4');

    // Area (green above zero, red below)
    const areaAbove = d3.area()
      .x(d => x(parseDate(d.date)))
      .y0(y(0))
      .y1(d => y(Math.max(d.value, 0)))
      .curve(d3.curveMonotoneX);
    const areaBelow = d3.area()
      .x(d => x(parseDate(d.date)))
      .y0(y(0))
      .y1(d => y(Math.min(d.value, 0)))
      .curve(d3.curveMonotoneX);

    g.append('path').datum(data)
      .attr('d', areaAbove)
      .attr('fill', C.green).attr('fill-opacity', 0.15);
    g.append('path').datum(data)
      .attr('d', areaBelow)
      .attr('fill', C.red).attr('fill-opacity', 0.15);

    // Line
    const line = d3.line()
      .x(d => x(parseDate(d.date)))
      .y(d => y(d.value))
      .curve(d3.curveMonotoneX);
    g.append('path').datum(data)
      .attr('d', line)
      .attr('fill', 'none')
      .attr('stroke', data[data.length-1].value >= 0 ? C.green : C.red)
      .attr('stroke-width', 2);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${ih})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.timeFormat('%b %d')))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);
    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => '$' + d3.format(',.0f')(d)))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);

    // Tooltip
    const tooltip = d3.select(el).append('div').attr('class', 'd3-tooltip');
    const bisect = d3.bisector(d => parseDate(d.date)).left;
    const overlay = g.append('rect')
      .attr('width', iw).attr('height', ih)
      .attr('fill', 'none').attr('pointer-events', 'all');
    const focus = g.append('circle').attr('r', 4)
      .attr('fill', C.textLight).attr('display', 'none');

    overlay.on('mousemove', function(event) {
      const [mx] = d3.pointer(event);
      const x0 = x.invert(mx);
      const i = bisect(data, x0, 1);
      const d0 = data[i-1], d1 = data[i];
      if (!d0) return;
      const d = d1 && (x0 - parseDate(d0.date) > parseDate(d1.date) - x0) ? d1 : d0;
      focus.attr('cx', x(parseDate(d.date))).attr('cy', y(d.value)).attr('display', null);
      const dt = new Date(d.date);
      tooltip.style('opacity', 1)
        .html(`<div>${dt.toLocaleDateString('en', {month:'short',day:'numeric'})} ${dt.toLocaleTimeString('en', {hour:'2-digit',minute:'2-digit'})}</div><div style="font-weight:700;color:${d.value >= 0 ? C.green : C.red}">$${d.value.toFixed(2)}</div>`)
        .style('left', (event.offsetX + 12) + 'px')
        .style('top', (event.offsetY - 28) + 'px');
    }).on('mouseleave', function() {
      focus.attr('display', 'none');
      tooltip.style('opacity', 0);
    });
  }

  function renderWaterfall(el, data) {
    if (!data || data.length < 2) {
      el.innerHTML = '<div class="chart-empty">Not enough data for chart.</div>';
      return;
    }
    const margin = {top: 16, right: 16, bottom: 32, left: 56};
    const width = el.clientWidth || 860;
    const height = 220;
    const iw = width - margin.left - margin.right;
    const ih = height - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const parseDate = d => new Date(d);
    const x = d3.scaleBand()
      .domain(data.map((d,i) => i))
      .range([0, iw]).padding(0.3);
    const yMin = Math.min(d3.min(data, d => d.cumulative), 0);
    const yMax = Math.max(d3.max(data, d => d.cumulative), 0);
    const yPad = (yMax - yMin) * 0.1 || 10;
    const y = d3.scaleLinear()
      .domain([yMin - yPad, yMax + yPad]).range([ih, 0]);

    // Zero line
    g.append('line')
      .attr('x1', 0).attr('x2', iw)
      .attr('y1', y(0)).attr('y2', y(0))
      .attr('stroke', C.zero).attr('stroke-width', 1)
      .attr('stroke-dasharray', '6,4');

    // Bars
    g.selectAll('.bar').data(data).enter().append('rect')
      .attr('x', (d,i) => x(i))
      .attr('width', x.bandwidth())
      .attr('y', d => y(Math.max(d.cumulative, d.cumulative - d.profit)))
      .attr('height', d => Math.max(1, Math.abs(y(0) - y(Math.abs(d.profit)))))
      .attr('fill', d => d.won ? C.green : C.red)
      .attr('rx', 2);

    // Cumulative line
    const line = d3.line()
      .x((d,i) => x(i) + x.bandwidth()/2)
      .y(d => y(d.cumulative))
      .curve(d3.curveMonotoneX);
    g.append('path').datum(data)
      .attr('d', line).attr('fill', 'none')
      .attr('stroke', C.line).attr('stroke-width', 1.5);

    // Axes
    const tickInterval = Math.max(1, Math.floor(data.length / 6));
    g.append('g')
      .attr('transform', `translate(0,${ih})`)
      .call(d3.axisBottom(d3.scaleBand().domain(
        data.filter((d,i) => i % tickInterval === 0).map((d,i) => {
          const dt = new Date(d.date);
          return dt.toLocaleDateString('en', {month:'short',day:'numeric'});
        })
      ).range([0, iw])))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);
    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => '$' + d3.format(',.0f')(d)))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);
  }

  function renderRollingAccuracy(el, data) {
    if (!data || data.length < 2) {
      el.innerHTML = '<div class="chart-empty">Not enough data for chart.</div>';
      return;
    }
    const margin = {top: 16, right: 16, bottom: 32, left: 48};
    const width = el.clientWidth || 860;
    const height = 200;
    const iw = width - margin.left - margin.right;
    const ih = height - margin.top - margin.bottom;

    const svg = d3.select(el).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const parseDate = d => new Date(d);
    const x = d3.scaleTime()
      .domain(d3.extent(data, d => parseDate(d.date)))
      .range([0, iw]);
    const y = d3.scaleLinear().domain([0, 100]).range([ih, 0]);

    // 50% baseline
    g.append('line')
      .attr('x1', 0).attr('x2', iw)
      .attr('y1', y(50)).attr('y2', y(50))
      .attr('stroke', C.zero).attr('stroke-width', 1)
      .attr('stroke-dasharray', '6,4');
    g.append('text')
      .attr('x', iw - 4).attr('y', y(50) - 4)
      .attr('text-anchor', 'end').attr('fill', C.text)
      .attr('font-size', '10px').text('50%');

    // Area above 50%
    const areaAbove = d3.area()
      .x(d => x(parseDate(d.date)))
      .y0(y(50))
      .y1(d => y(Math.max(d.value, 50)))
      .curve(d3.curveMonotoneX);
    g.append('path').datum(data)
      .attr('d', areaAbove)
      .attr('fill', C.green).attr('fill-opacity', 0.1);

    // Line
    const line = d3.line()
      .x(d => x(parseDate(d.date)))
      .y(d => y(d.value))
      .curve(d3.curveMonotoneX);
    g.append('path').datum(data)
      .attr('d', line).attr('fill', 'none')
      .attr('stroke', C.line).attr('stroke-width', 2);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${ih})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.timeFormat('%b %d')))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);
    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => d + '%'))
      .attr('color', C.text).attr('font-size', '10px')
      .select('.domain').attr('stroke', C.grid);
  }

  // Dispatcher
  document.addEventListener('DOMContentLoaded', function() {
    const renderers = {
      cumulative_pnl: renderCumulativePnl,
      waterfall: renderWaterfall,
      rolling_accuracy: renderRollingAccuracy
    };
    document.querySelectorAll('.d3-chart').forEach(function(el) {
      const type = el.dataset.chartType;
      try {
        const data = JSON.parse(el.dataset.chartData);
        if (renderers[type]) renderers[type](el, data);
      } catch(e) {
        el.innerHTML = '<div class="chart-empty">Chart unavailable.</div>';
      }
    });
  });
})();
</script>
"""


def nav_html(nav_links, active_label=""):
    """Render the navigation bar."""
    items = []
    for link in nav_links:
        cls = ' class="active"' if link["label"] == active_label else ""
        items.append(f'<a href="{link["href"]}"{cls}>{link["label"]}</a>')
    return f'<nav class="nav">{" ".join(items)}</nav>'


def page_shell(title, body_html, nav_links, active_label=""):
    """Wrap body content in the full HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css()}</style>
</head>
<body>
<div class="container">
{nav_html(nav_links, active_label)}
{body_html}
<div class="footer">Generated {_now_utc_str()} UTC</div>
</div>
{d3_script()}
</body>
</html>"""


def _now_utc_str():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
