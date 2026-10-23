"""Data-quality checks. Each check returns a list of issues; nothing is silently dropped."""
import pandas as pd

NOTATION_KEYS = {"NO", "IE", "NE", "C"}   # not occurring, included elsewhere, not estimated, confidential
ALLOWED_UNITS = {"TJ", "t", "MWh"}
QUALITY_TIERS = {"H", "M", "L"}


def _issue(row, check, severity, message):
    return {"year": row.year, "gpc_ref": row.gpc_ref, "fuel": row.fuel,
            "check": check, "severity": severity, "message": message}


def check_activity(activity: pd.DataFrame, factors: pd.DataFrame) -> list[dict]:
    issues = []
    known = set(zip(factors["fuel"], factors["use"]))
    for row in activity.itertuples(index=False):
        has_key = not pd.isna(row.notation_key)
        has_value = not pd.isna(row.activity_value)
        if has_key and row.notation_key not in NOTATION_KEYS:
            issues.append(_issue(row, "notation_key", "error", f"unknown notation key {row.notation_key!r}"))
        if has_key and has_value:
            issues.append(_issue(row, "notation_key", "error", "row has both a value and a notation key"))
        if not has_key and not has_value:
            issues.append(_issue(row, "missing", "error", "no value and no notation key"))
        if has_key and pd.isna(row.comment):
            issues.append(_issue(row, "notation_key", "warning", "notation key without an explanation"))
        if not has_value:
            continue
        if row.activity_value < 0:
            issues.append(_issue(row, "range", "error", "negative activity value"))
        if row.activity_unit not in ALLOWED_UNITS:
            issues.append(_issue(row, "unit", "error", f"unsupported unit {row.activity_unit!r}"))
        if (row.fuel, row.use) not in known:
            issues.append(_issue(row, "factor", "error", f"no emission factor for {row.fuel}/{row.use}"))
        if row.data_quality not in QUALITY_TIERS:
            issues.append(_issue(row, "data_quality", "warning", "data quality tier not set (H/M/L)"))
    return issues


def check_year_on_year(activity: pd.DataFrame, year: int, threshold: float = 0.30) -> list[dict]:
    """Flag activity that changes by more than `threshold` against the previous year."""
    issues = []
    cur = activity[activity["year"] == year].dropna(subset=["activity_value"])
    prev = activity[activity["year"] == year - 1].dropna(subset=["activity_value"])
    merged = cur.merge(prev, on=["gpc_ref", "fuel", "use"], suffixes=("", "_prev"))
    for row in merged.itertuples(index=False):
        change = row.activity_value / row.activity_value_prev - 1
        if abs(change) > threshold:
            issues.append(_issue(row, "year_on_year", "warning",
                                 f"activity changed {change:+.0%} vs {year - 1}; confirm with data provider"))
    return issues
