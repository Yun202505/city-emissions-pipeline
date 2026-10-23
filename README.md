# city-emissions-pipeline

A small, reproducible pipeline that builds a city greenhouse-gas inventory following the
[GHG Protocol for Cities (GPC)](https://ghgprotocol.org/ghg-protocol-cities). It is a worked example of
how I structure emissions data: activity data and emission factors kept apart, every result tied to the
factor catalogue and GWP set that produced it, and data-quality checks run before anything is reported.

The emission factors and GWP values are public IPCC defaults. **The activity data for "Example City" are
illustrative**, made up to exercise the pipeline, and do not describe a real city.

## What it does

```
activity data ──► QA checks ──► activity × emission factor ──► CO2e (chosen GWP set) ──► GPC sector/scope
 (city CSV)       (errors stop     (IPCC 2006 defaults,          (AR4 / AR5 / AR6)          tables + BASIC
                   the run)          versioned catalogue)                                     coverage check
                                                                       │
                                                                       └──► manifest.json: input file hashes,
                                                                            catalogue version, GWP set, git commit
```

- **Calculation** – fuel use in tonnes is converted to energy with the IPCC net calorific value, then
  multiplied by CO2, CH4 and N2O factors and converted to CO2e. Grid electricity uses a CO2e factor directly.
- **GPC reporting rules** – each row has a GPC reference number (e.g. `I.1.1` residential fuel combustion,
  scope 1). The coverage check confirms that every reference required for BASIC (or BASIC+) has either a
  number or a notation key: `NO` not occurring, `IE` included elsewhere, `NE` not estimated, `C` confidential.
- **Reproducibility** – factor catalogues are never edited in place; a change is a new file
  (`ipcc2006_v1.csv` → `ipcc2006_v2.csv`). Results carry the catalogue version and SHA-256 hash, and each run
  writes a manifest, so a stored inventory can be rebuilt exactly after the catalogue has moved on.
- **Data quality** – runs stop on errors (negative values, unknown units, a value *and* a notation key,
  missing factors) and record warnings (notation keys without an explanation, missing quality tier,
  year-on-year changes above 30%).

## Run it

```bash
pip install -e ".[test]"
python -m city_ghg.run --year 2023                 # writes outputs/2023/
python -m city_ghg.run --year 2023 --gwp AR6       # same inventory with AR6 GWPs
python -m pytest                                   # hand-checked unit tests
```

Example output for 2023 (AR5, catalogue v1):

| Sector | Scope | t CO2e |
|---|---|---:|
| Stationary energy | 1 | 372,143 |
| Stationary energy | 2 | 1,040,000 |
| Transportation | 1 | 1,087,006 |
| Transportation | 2 | NE |
| Waste | 1 | NE |
| Waste | 3 | NO |

The QA report flags one warning: on-road diesel sales rose 61% from 2022, which the data note attributes to a
new fuel depot entering the sales data. That is a number to confirm with the data provider before publishing,
not one to report silently.

### Rebuilding an old inventory after the catalogue changes

```bash
python -m city_ghg.run --year 2023 --catalogue data/factors/ipcc2006_v2.csv --out outputs/v2
python -m city_ghg.run --year 2023 --reproduce outputs/2023/manifest.json
# reproduced total 2,499,148.9 t CO2e; difference vs stored 0.000000 t
```

The v2 catalogue has a lower grid factor and gives a different total, while the original v1 inventory is
still reproduced exactly from its manifest. If an input file has been edited since the original run, the
hash check stops the rebuild.

## Layout

```
data/
  factors/ipcc2006_v1.csv, ipcc2006_v2.csv   emission-factor catalogues (one file per version)
  factors/gwp.csv                            AR4, AR5, AR6 100-year GWPs
  gpc_reference.csv                          GPC reference numbers, sectors, scopes, BASIC / BASIC+
  example_city/activity.csv                  illustrative activity data, 2022–2023
src/city_ghg/
  catalogue.py   load catalogues and GWP sets, hash files
  calculate.py   activity × factor → gas → CO2e, with factor IDs on every row
  quality.py     data-quality checks
  gpc.py         sector/scope summary and BASIC coverage
  run.py         command line: build, write outputs and manifest, reproduce
tests/           unit tests checked against hand calculations
```

## Sources

- IPCC (2006) *Guidelines for National Greenhouse Gas Inventories*, Vol. 2 Energy: Tables 1.2 (net calorific
  values), 2.4–2.5 (stationary combustion), 3.2.1–3.2.2 (road transport).
- IPCC AR4 WG1 Table 2.14, AR5 WG1 Table 8.7, AR6 WG1 Table 7.15 (100-year GWPs; AR6 CH4 uses the fossil value).
- WRI, C40 and ICLEI (2014) *Global Protocol for Community-Scale Greenhouse Gas Emission Inventories*.

The grid electricity factor (0.40 and 0.35 kg CO2e/kWh) is a placeholder and should be replaced with a
local or national value.

## Scope and limits

This is deliberately small: two sectors calculated, waste and IPPU shown only through notation keys, and no
database or orchestration layer. In production the same structure would sit in tables with the factor
catalogue as a versioned reference table and the manifest fields stored alongside each inventory.
