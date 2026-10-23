"""Emissions = activity data x emission factor, converted to CO2e with a chosen GWP set.

Every result row carries the factor IDs, catalogue version/hash and GWP set used,
so a stored inventory can be reproduced after the catalogue changes.
"""
import pandas as pd

from .catalogue import Catalogue

GASES = ["CO2", "CH4", "N2O"]


def to_tj(value: float, unit: str, ncv_tj_per_gg: float) -> float:
    """Convert fuel activity to energy (TJ). Mass is converted with the net calorific value."""
    if unit == "TJ":
        return value
    if unit == "t":
        return value / 1000 * ncv_tj_per_gg   # t -> Gg, then x TJ/Gg
    raise ValueError(f"unsupported fuel unit {unit!r}")


def _fuel_row(row, factors: pd.DataFrame, gwp: dict) -> dict:
    f = factors[(factors["fuel"] == row.fuel) & (factors["use"] == row.use)].set_index("gas")
    if not set(GASES) <= set(f.index):
        raise KeyError(f"no complete CO2/CH4/N2O factors for {row.fuel}/{row.use}")
    energy_tj = to_tj(row.activity_value, row.activity_unit, f.loc["CO2", "ncv_tj_per_gg"])
    out = {"energy_tj": energy_tj}
    co2e_t = 0.0
    for gas in GASES:
        t = energy_tj * f.loc[gas, "value"] / 1000          # kg/TJ x TJ -> t
        out[f"{gas.lower()}_t"] = t
        co2e_t += t * gwp[gas]
    out["co2e_t"] = co2e_t
    out["factor_ids"] = ";".join(f.loc[GASES, "factor_id"])
    return out


def _grid_row(row, factors: pd.DataFrame) -> dict:
    if row.activity_unit != "MWh":
        raise ValueError(f"grid electricity must be in MWh, got {row.activity_unit!r}")
    f = factors[(factors["fuel"] == "grid_electricity") & (factors["gas"] == "CO2e")].iloc[0]
    # The grid factor is already in CO2e, so the GWP set is not applied again here.
    return {"co2e_t": row.activity_value * 1000 * f["value"] / 1000,   # MWh -> kWh, kg -> t
            "factor_ids": f["factor_id"]}


def calculate(activity: pd.DataFrame, catalogue: Catalogue, gwp: dict, gwp_set: str) -> pd.DataFrame:
    """Return one result row per activity row. Rows with a notation key keep the key and no number."""
    rows = []
    for row in activity.itertuples(index=False):
        res = {"city": row.city, "year": row.year, "gpc_ref": row.gpc_ref, "fuel": row.fuel,
               "notation_key": row.notation_key, "data_quality": row.data_quality}
        if pd.isna(row.notation_key):
            if row.fuel == "grid_electricity":
                res.update(_grid_row(row, catalogue.factors))
            else:
                res.update(_fuel_row(row, catalogue.factors, gwp))
        rows.append(res)
    out = pd.DataFrame(rows)
    out["catalogue_version"] = catalogue.version
    out["catalogue_sha256"] = catalogue.sha256
    out["gwp_set"] = gwp_set
    return out
