"""GPC reporting rules: map results to sectors/scopes and check BASIC / BASIC+ coverage."""
import pandas as pd


def load_reference(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"scope": int})


def coverage(results: pd.DataFrame, reference: pd.DataFrame, level: str = "BASIC") -> pd.DataFrame:
    """Every GPC reference required at `level` must have a number or a notation key."""
    levels = ["BASIC"] if level == "BASIC" else ["BASIC", "BASIC+"]
    required = reference[reference["level"].isin(levels)]
    reported = results.groupby("gpc_ref").agg(
        co2e_t=("co2e_t", lambda s: s.sum(min_count=1)),
        notation_key=("notation_key", lambda s: ",".join(sorted(set(s.dropna())))),
    )
    out = required.merge(reported, left_on="gpc_ref", right_index=True, how="left")
    out["status"] = "reported"
    out.loc[out["co2e_t"].isna() & (out["notation_key"].fillna("") != ""), "status"] = "notation key"
    out.loc[out["co2e_t"].isna() & (out["notation_key"].fillna("") == ""), "status"] = "MISSING"
    return out


def summary(results: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Total CO2e by GPC sector and scope."""
    df = results.merge(reference[["gpc_ref", "sector", "scope"]], on="gpc_ref", how="left")
    return (df.groupby(["sector", "scope"], as_index=False)["co2e_t"].sum(min_count=1)
              .sort_values(["sector", "scope"]))
