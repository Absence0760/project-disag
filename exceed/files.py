"""File I/O for exceed tool."""

from typing import Dict, List

from disag.files import (
    read_daily_file as _read_daily_records,
    read_monthly_file as _read_monthly_records,
)


def read_monthly_file(filepath: str) -> Dict[int, List[float]]:
    """
    Read monthly flow data file and group values by calendar month.

    Delegates to disag.files.read_monthly_file for parsing — the same
    reason we delegate .day reading: that reader handles the fixed-width
    column collision in wet-year rows (e.g. ``14639.12013670.740``) and
    2/4-digit year normalisation, which a ``.split()``-based parser here
    would silently drop. Negative (missing-data) values are excluded; the
    exceed tool does not patch.

    Returns:
        Dictionary mapping calendar month (1-12) to list of flow values.
    """
    monthly_data: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
    for (_year, month), value in _read_monthly_records(filepath).items():
        if value >= 0:
            monthly_data[month].append(value)
    return monthly_data


def read_daily_file(filepath: str) -> Dict[int, List[float]]:
    """
    Read daily flow data file and group values by calendar month.

    Delegates to disag.files.read_daily_file for the fixed-width parsing
    (handles 2- and 4-digit years, no-space negative values, and the
    monthly-total header line) and then strips MISSING values.

    Returns:
        Dictionary mapping calendar month (1-12) to list of daily flow values
        (missing values excluded).
    """
    daily_data: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
    records = _read_daily_records(filepath)

    # Spec: any negative value is the missing-data sentinel (docs/file-formats.md).
    # Drop them before exceedance analysis; the exceed tool does not patch.
    for (_year, month), rec in records.items():
        for v in rec.v:
            if v >= 0:
                daily_data[month].append(v)

    return daily_data


def write_exceedance_report(filepath: str, monthly_exceedance: Dict) -> None:
    """
    Write exceedance analysis report to file.

    Accepts monthly results keyed by calendar-month int (1-12) and daily
    results keyed by string `daily_<month>` (e.g. `daily_1` for January).
    Monthly sections are written first, followed by daily sections.

    Args:
        filepath: Output file path
        monthly_exceedance: Dict mapping either int month or `daily_<month>`
            string to {flow_values, exceedance_pct, ...}
    """
    from datetime import datetime

    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']

    def _write_section(f, heading, result):
        f.write(f'{heading}\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total values: {result["total_count"]}  '
               f'Below range: {result["count_below"]}  '
               f'Above range: {result["count_above"]}\n\n')

        f.write('Exceedance%    Flow Value\n')
        f.write('-' * 30 + '\n')

        flows = result['flow_values']
        exceedances = result['exceedance_pct']

        for i in range(len(flows)):
            f.write(f'{exceedances[i]:8.2f}%     {flows[i]:12.3f}\n')

        f.write('\n')

    with open(filepath, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Exceedance Analysis Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('-' * 80 + '\n\n')

        for month in range(1, 13):
            if month not in monthly_exceedance:
                continue
            _write_section(f, f'MONTHLY - {month_names[month].upper()}',
                           monthly_exceedance[month])

        for month in range(1, 13):
            key = f'daily_{month}'
            if key not in monthly_exceedance:
                continue
            _write_section(f, f'DAILY - {month_names[month].upper()}',
                           monthly_exceedance[key])


_MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']

# Distinct, print-friendly hues so overlaid curves stay legible.
_SVG_COLORS = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#0891b2',
               '#db2777', '#65a30d', '#ea580c', '#4f46e5', '#0d9488', '#9333ea']


def _series_label(key) -> str:
    """Human label for a series key (int month, ``daily_<m>``, or season name)."""
    if isinstance(key, int):
        return _MONTH_NAMES[key] if 1 <= key <= 12 else str(key)
    if isinstance(key, str) and key.startswith('daily_'):
        try:
            return 'Daily ' + _MONTH_NAMES[int(key.split('_', 1)[1])]
        except (ValueError, IndexError):
            return key
    return str(key)


def _xml_escape(text: str) -> str:
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def write_exceedance_svg(
    filepath: str,
    exceedance: Dict,
    title: str = 'Flow-frequency curve',
) -> None:
    """Render the exceedance curves as a standalone SVG (stdlib only).

    Plots flow (y) against exceedance percentage (x, 0–100), one polyline
    per series, with axes, gridlines, and a legend. Accepts the same dicts
    as the report writers: keys may be int calendar months, ``daily_<m>``
    strings, or season names.
    """
    # Stable display order: calendar months, then daily months, then seasons.
    int_keys = sorted(k for k in exceedance if isinstance(k, int))
    daily_keys = sorted(
        (k for k in exceedance if isinstance(k, str) and k.startswith('daily_')),
        key=lambda k: int(k.split('_', 1)[1]) if k.split('_', 1)[1].isdigit() else 99,
    )
    season_keys = [
        k for k in exceedance
        if isinstance(k, str) and not k.startswith('daily_')
    ]
    keys = int_keys + daily_keys + season_keys

    series = []
    ymax = 0.0
    for k in keys:
        r = exceedance[k]
        pts = sorted(zip(r['exceedance_pct'], r['flow_values']))
        if not pts:
            continue
        series.append((k, pts))
        ymax = max(ymax, max(f for _, f in pts))
    if ymax <= 0:
        ymax = 1.0

    W, H = 900, 560
    ml, mr, mt, mb = 72, 210, 52, 62
    pw, ph = W - ml - mr, H - mt - mb

    def sx(x: float) -> float:
        return ml + (x / 100.0) * pw

    def sy(y: float) -> float:
        return mt + ph - (y / ymax) * ph

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">'
    )
    out.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    out.append(
        f'<text x="{ml}" y="28" font-size="17" font-weight="bold" '
        f'fill="#0f172a">{_xml_escape(title)}</text>'
    )

    # Gridlines + axis ticks
    for i in range(11):  # x: 0..100 every 10%
        x = sx(i * 10)
        out.append(
            f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt + ph}" '
            f'stroke="#e2e8f0"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{mt + ph + 18}" text-anchor="middle" '
            f'fill="#475569">{i * 10}</text>'
        )
    for j in range(6):  # y: 0..ymax in 5 steps
        val = ymax * j / 5
        y = sy(val)
        out.append(
            f'<line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" '
            f'stroke="#e2e8f0"/>'
        )
        out.append(
            f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#475569">{val:.1f}</text>'
        )

    # Axis labels
    out.append(
        f'<text x="{ml + pw / 2:.0f}" y="{H - 16}" text-anchor="middle" '
        f'fill="#0f172a">Exceedance (%)</text>'
    )
    out.append(
        f'<text x="18" y="{mt + ph / 2:.0f}" text-anchor="middle" '
        f'fill="#0f172a" transform="rotate(-90 18 {mt + ph / 2:.0f})">'
        f'Flow</text>'
    )

    # Curves + legend
    for idx, (key, pts) in enumerate(series):
        color = _SVG_COLORS[idx % len(_SVG_COLORS)]
        poly = ' '.join(f'{sx(x):.1f},{sy(y):.1f}' for x, y in pts)
        out.append(
            f'<polyline points="{poly}" fill="none" stroke="{color}" '
            f'stroke-width="2"/>'
        )
        ly = mt + 6 + idx * 20
        out.append(
            f'<line x1="{ml + pw + 18}" y1="{ly}" x2="{ml + pw + 42}" '
            f'y2="{ly}" stroke="{color}" stroke-width="3"/>'
        )
        out.append(
            f'<text x="{ml + pw + 48}" y="{ly + 4}" fill="#0f172a">'
            f'{_xml_escape(_series_label(key))}</text>'
        )

    out.append('</svg>')
    with open(filepath, 'w') as f:
        f.write('\n'.join(out))


def write_seasonal_exceedance_report(
    filepath: str,
    seasonal_exceedance: Dict[str, Dict]
) -> None:
    """
    Write seasonal exceedance analysis report to file.
    
    Args:
        filepath: Output file path
        seasonal_exceedance: Dict mapping season name to exceedance data
    """
    from datetime import datetime
    
    with open(filepath, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Seasonal Exceedance Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('-' * 80 + '\n\n')
        
        for season_name in sorted(seasonal_exceedance.keys()):
            result = seasonal_exceedance[season_name]
            f.write(f'{season_name.upper()}\n')
            f.write('-' * 80 + '\n')
            f.write(f'Total values: {result["total_count"]}  '
                   f'Below range: {result["count_below"]}  '
                   f'Above range: {result["count_above"]}\n\n')
            
            f.write('Exceedance%    Flow Value\n')
            f.write('-' * 30 + '\n')
            
            flows = result['flow_values']
            exceedances = result['exceedance_pct']
            
            for i in range(len(flows)):
                f.write(f'{exceedances[i]:8.2f}%     {flows[i]:12.3f}\n')
            
            f.write('\n')


