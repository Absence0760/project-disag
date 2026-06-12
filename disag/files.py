"""
File I/O for NS flow data files.

Daily files (.day):   12-line header, then one record per month.
Monthly files (.mon): 5-line header, then one record per hydro year (Oct-Sep).

Daily record layout
-------------------
  Line 0 : <year:≥3> <month:≥2> [<total_Mm3:10.3f>]
  Lines 1-4 : 7 values × 7-char fixed-width each (days 1-28)
  Line 5 :   remaining days for 29/30/31-day months; blank for 28-day months

Monthly record layout
---------------------
  One line: <year> <v1> <v2> … <v12>   (hydro order: Oct … Sep)
"""

import calendar
import os
from dataclasses import dataclass
from datetime import datetime

MISSING = -99.99
DAILY_HEADER_LINES = 12
MONTHLY_HEADER_LINES = 5
MONTHLY_VAL_WIDTH = 9  # width of each .mon value column (contiguous, right-justified)


@dataclass
class DailyRecord:
    year: int
    month: int
    v: list  # float, length == dim; m3/s (or MISSING for no-data)

    @property
    def dim(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def read_daily_file(path: str) -> dict:
    """Read a daily flow file.

    Returns
    -------
    dict  {(year, month): DailyRecord}
    """
    records = {}
    with open(path) as fh:
        for _ in range(DAILY_HEADER_LINES):
            fh.readline()

        while True:
            header = fh.readline()
            if not header:
                break
            header = header.rstrip('\n')
            if not header.strip():
                continue

            parts = header.split()
            if len(parts) < 2:
                continue

            year = int(parts[0])
            month = int(parts[1])
            if year < 1900:
                year += 1900

            dim = calendar.monthrange(year, month)[1]

            # Days 1-28: always 4 lines of exactly 7 values (7 chars each)
            values = []
            for _ in range(4):
                line = fh.readline().rstrip('\n')
                for i in range(0, 49, 7):           # 7 values × 7 chars = 49
                    chunk = line[i:i + 7].strip() if i < len(line) else ''
                    try:
                        values.append(float(chunk))
                    except ValueError:
                        values.append(MISSING)

            if dim == 28:
                fh.readline()                       # extra blank line
            else:
                # Days 29-dim on one more line
                line = fh.readline().rstrip('\n')
                extras = dim - 28
                for i in range(0, extras * 7, 7):
                    chunk = line[i:i + 7].strip() if i < len(line) else ''
                    try:
                        values.append(float(chunk))
                    except ValueError:
                        values.append(MISSING)

            records[(year, month)] = DailyRecord(year=year, month=month, v=values[:dim])

    return records


def _parse_monthly_values(parts: list, line: str):
    """Return the 12 monthly values from a .mon data line, or ``None``.

    Normal rows are whitespace-separated, so ``parts[1:13]`` is enough.
    But .mon values are written as contiguous 9-char columns, and in a
    wet year two adjacent full-width fields touch with no separator
    (e.g. ``14639.12013670.740``) — the same fixed-width trap documented
    for .day files. Those rows have fewer than 13 tokens, so we re-slice
    the final twelve 9-char columns by position.
    """
    if len(parts) >= 13:
        try:
            return [float(x) for x in parts[1:13]]
        except ValueError:
            pass
    # rstrip() (not just '\n') so trailing spaces can't shift the column
    # offsets — the twelve values are the final 9-char fields of the row.
    body = line.rstrip()
    span = 12 * MONTHLY_VAL_WIDTH
    if len(body) < span:
        return None
    region = body[-span:]
    try:
        return [
            float(region[i * MONTHLY_VAL_WIDTH:(i + 1) * MONTHLY_VAL_WIDTH])
            for i in range(12)
        ]
    except ValueError:
        return None


def read_monthly_file(path: str) -> dict:
    """Read a monthly flow file (hydro-year records, Oct-Sep).

    Returns
    -------
    dict  {(calendar_year, calendar_month): flow_Mm3}
    """
    result = {}
    with open(path) as fh:
        for _ in range(MONTHLY_HEADER_LINES):
            fh.readline()

        span = 12 * MONTHLY_VAL_WIDTH
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            # Parse the year. Whitespace-separated rows give a clean
            # parts[0], so try that first. Only fall back to a positional
            # slice when it fails: in a fixed-width wet year October's
            # full-width value fuses with the 4-char year
            # (e.g. '199114639.120…'), so parts[0] is unparseable and the
            # year lives in the columns *before* the twelve value fields —
            # the same fixed-width trap _parse_monthly_values guards on the
            # value side. Trying the positional slice first would instead
            # drop ragged large-value rows (line longer than the value span
            # but not column-aligned), so order matters here.
            try:
                hydro_year = int(parts[0])
            except ValueError:
                body = line.rstrip()
                year_field = body[:-span] if len(body) > span else parts[0]
                try:
                    hydro_year = int(year_field)
                except ValueError:
                    continue
            if hydro_year < 1900:
                hydro_year += 1900
            vals = _parse_monthly_values(parts, line)
            if vals is None:
                continue

            # Map hydro months (Oct=0 … Sep=11) to calendar (year, month)
            cal_dates = [
                (hydro_year,     10), (hydro_year,     11), (hydro_year,     12),
                (hydro_year + 1,  1), (hydro_year + 1,  2), (hydro_year + 1,  3),
                (hydro_year + 1,  4), (hydro_year + 1,  5), (hydro_year + 1,  6),
                (hydro_year + 1,  7), (hydro_year + 1,  8), (hydro_year + 1,  9),
            ]
            for (cy, cm), v in zip(cal_dates, vals):
                result[(cy, cm)] = v

    return result


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_daily_file(path: str, records: list, header_info: dict) -> None:
    """Write a list of DailyRecord objects to a .day file (12-line header).

    ``header_info['run_date']`` is honoured if present (used by mock-data
    generators that want byte-stable output); otherwise ``datetime.now()``
    is used.
    """
    dash = '-' * 80
    run_date = header_info.get('run_date') or (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open(path, 'w') as fh:
        # 12-line header (must match DAILY_HEADER_LINES so readers skip it)
        fh.write(dash + '\n')                                                   # 1
        fh.write(f'Description   : {os.path.basename(path)}\n')                # 2
        fh.write('Units         : m3/s\n')                                      # 3
        fh.write(f'Disaggregated    (monthly) : '
                 f'{header_info.get("monthly_file", "")}\n')                    # 4
        fh.write(f'Disaggregator,1  (daily  ) : '
                 f'{header_info.get("daily_file_1", "")}\n')                    # 5
        fh.write(f'Disaggregator,2  (daily  ) : '
                 f'{header_info.get("daily_file_2", "")}\n')                    # 6
        fh.write(f'Disag method  : {header_info.get("method_str", "")}\n')     # 7
        fh.write('-\n')                                                          # 8
        fh.write('-\n')                                                          # 9
        fh.write(f'Run Date      : {run_date}\n')                                # 10
        fh.write(dash + '\n')                                                   # 11
        fh.write('\n')                                                           # 12

        for rec in records:
            _write_daily_record(fh, rec)


def _write_daily_record(fh, rec: DailyRecord) -> None:
    dim = rec.dim
    total = sum(rec.v[:dim])                    # sum may include MISSING values
    total_mm3 = total / 1e6 * 3600 * 24        # m3/s → Mm3/month
    if total_mm3 < 0:
        total_mm3 = MISSING

    fh.write(f'{rec.year:3d}{rec.month:3d}{total_mm3:10.3f}\n')

    for dd in range(1, dim + 1):
        v = rec.v[dd - 1]
        if v < 0:
            decimals = 2
        elif v > 999:
            decimals = 1
        elif v > 99:
            decimals = 2
        else:
            decimals = 3
        fh.write(f'{v:7.{decimals}f}')
        if dd % 7 == 0:
            fh.write('\n')

    fh.write('\n')          # terminates final partial line (or blank for DIM=28)
