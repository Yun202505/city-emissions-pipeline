"""Build one city inventory year and write results, QA report and a run manifest.

    python -m city_ghg.run --year 2023
    python -m city_ghg.run --year 2023 --reproduce outputs/2023/manifest.json
"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import calculate, gpc, quality
from .catalogue import file_sha256, load_catalogue, load_gwp

ROOT = Path(__file__).resolve().parents[2]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build(year, activity_path, catalogue_path, gwp_path, gwp_set, reference_path):
    activity = pd.read_csv(activity_path)
    cat = load_catalogue(catalogue_path)
    issues = quality.check_activity(activity[activity["year"] == year], cat.factors)
    issues += quality.check_year_on_year(activity, year)
    errors = [i for i in issues if i["severity"] == "error"]
    if errors:
        raise SystemExit(f"{len(errors)} data errors, inventory not built:\n" + pd.DataFrame(errors).to_string())
    results = calculate.calculate(activity[activity["year"] == year], cat, load_gwp(gwp_path, gwp_set), gwp_set)
    ref = gpc.load_reference(reference_path)
    return results, pd.DataFrame(issues), gpc.coverage(results, ref), gpc.summary(results, ref), cat


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--activity", default=ROOT / "data/example_city/activity.csv")
    p.add_argument("--catalogue", default=ROOT / "data/factors/ipcc2006_v1.csv")
    p.add_argument("--gwp", default="AR5")
    p.add_argument("--out", default=ROOT / "outputs")
    p.add_argument("--reproduce", help="manifest.json of an earlier run: rebuild with its inputs and compare")
    a = p.parse_args()

    if a.reproduce:
        m = json.loads(Path(a.reproduce).read_text())
        for key in ("activity", "catalogue"):
            if file_sha256(ROOT / m[key]["path"]) != m[key]["sha256"]:
                raise SystemExit(f"{m[key]['path']} has changed since the original run")
        results, *_ = build(m["year"], ROOT / m["activity"]["path"], ROOT / m["catalogue"]["path"],
                            ROOT / "data/factors/gwp.csv", m["gwp_set"], ROOT / "data/gpc_reference.csv")
        stored = pd.read_csv(Path(a.reproduce).parent / "inventory.csv")
        diff = abs(results["co2e_t"].sum() - stored["co2e_t"].sum())
        print(f"reproduced total {results['co2e_t'].sum():,.1f} t CO2e; difference vs stored {diff:.6f} t")
        return

    results, issues, cov, summ, cat = build(a.year, a.activity, a.catalogue, ROOT / "data/factors/gwp.csv",
                                            a.gwp, ROOT / "data/gpc_reference.csv")
    out = Path(a.out) / str(a.year)
    out.mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "inventory.csv", index=False)
    summ.to_csv(out / "summary_by_sector_scope.csv", index=False)
    cov.to_csv(out / "gpc_basic_coverage.csv", index=False)
    issues.to_csv(out / "qa_issues.csv", index=False)
    manifest = {
        "year": a.year,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_commit": git_commit(),
        "activity": {"path": Path(a.activity).resolve().relative_to(ROOT).as_posix(),
                     "sha256": file_sha256(a.activity)},
        "catalogue": {"path": cat.path.resolve().relative_to(ROOT).as_posix(),
                      "version": cat.version, "sha256": cat.sha256},
        "gwp_set": a.gwp,
        "total_co2e_t": round(float(results["co2e_t"].sum()), 3),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(summ.to_string(index=False))
    print(f"\nTotal: {manifest['total_co2e_t']:,.0f} t CO2e  ({cat.version}, GWP {a.gwp})")
    print(f"GPC BASIC coverage: {cov['status'].value_counts().to_dict()}")
    print(f"QA issues: {len(issues)} (see {out / 'qa_issues.csv'})")


if __name__ == "__main__":
    main()
