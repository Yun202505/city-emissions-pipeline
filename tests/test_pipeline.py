from pathlib import Path

import pandas as pd
import pytest

from city_ghg import calculate, gpc, quality
from city_ghg.catalogue import load_catalogue, load_gwp

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "data/factors/ipcc2006_v1.csv"
V2 = ROOT / "data/factors/ipcc2006_v2.csv"
GWP = ROOT / "data/factors/gwp.csv"


def row(**kw):
    base = dict(city="Test", year=2023, gpc_ref="I.1.1", fuel="natural_gas", use="stationary",
                activity_value=4000.0, activity_unit="TJ", notation_key=None, data_quality="H", comment=None)
    base.update(kw)
    return pd.DataFrame([base])


def test_natural_gas_matches_hand_calculation():
    # 4,000 TJ x (56,100 kg CO2 + 5 kg CH4 x 28 + 0.1 kg N2O x 265) per TJ
    res = calculate.calculate(row(), load_catalogue(V1), load_gwp(GWP, "AR5"), "AR5")
    assert res.loc[0, "co2e_t"] == pytest.approx(224_400 + 20 * 28 + 0.4 * 265)


def test_mass_is_converted_with_ncv():
    # 1,000 t diesel = 1 Gg x 43.0 TJ/Gg
    res = calculate.calculate(row(fuel="gas_diesel_oil", activity_value=1000, activity_unit="t"),
                              load_catalogue(V1), load_gwp(GWP, "AR5"), "AR5")
    assert res.loc[0, "energy_tj"] == pytest.approx(43.0)


def test_gwp_choice_changes_non_co2_only():
    cat = load_catalogue(V1)
    ar5 = calculate.calculate(row(), cat, load_gwp(GWP, "AR5"), "AR5").loc[0]
    ar6 = calculate.calculate(row(), cat, load_gwp(GWP, "AR6"), "AR6").loc[0]
    assert ar5["co2_t"] == ar6["co2_t"]
    assert ar6["co2e_t"] - ar5["co2e_t"] == pytest.approx(20 * (29.8 - 28) + 0.4 * (273 - 265))


def test_results_record_the_catalogue_they_used():
    grid = row(gpc_ref="I.1.2", fuel="grid_electricity", use="grid", activity_value=1000, activity_unit="MWh")
    old = calculate.calculate(grid, load_catalogue(V1), {}, "AR5").loc[0]
    new = calculate.calculate(grid, load_catalogue(V2), {}, "AR5").loc[0]
    assert old["co2e_t"] == pytest.approx(400) and new["co2e_t"] == pytest.approx(350)
    assert old["catalogue_version"] == "ipcc2006_v1" and new["catalogue_version"] == "ipcc2006_v2"
    assert old["catalogue_sha256"] != new["catalogue_sha256"]


def test_value_and_notation_key_together_is_an_error():
    issues = quality.check_activity(row(notation_key="NE", comment="x"), load_catalogue(V1).factors)
    assert any(i["severity"] == "error" for i in issues)


def test_year_on_year_jump_is_flagged():
    df = pd.concat([row(year=2022, activity_value=1000), row(year=2023, activity_value=1500)])
    assert len(quality.check_year_on_year(df, 2023)) == 1


def test_missing_basic_reference_is_reported():
    ref = gpc.load_reference(ROOT / "data/gpc_reference.csv")
    res = calculate.calculate(row(), load_catalogue(V1), load_gwp(GWP, "AR5"), "AR5")
    cov = gpc.coverage(res, ref).set_index("gpc_ref")
    assert cov.loc["I.1.1", "status"] == "reported"
    assert cov.loc["II.1.1", "status"] == "MISSING"
