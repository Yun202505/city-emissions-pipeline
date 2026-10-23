"""Load emission-factor catalogues and GWP sets, with a content hash for each catalogue."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

FACTOR_COLUMNS = ["factor_id", "fuel", "use", "gas", "value", "unit", "ncv_tj_per_gg", "source"]


@dataclass(frozen=True)
class Catalogue:
    path: Path
    version: str   # file stem, e.g. "ipcc2006_v1"
    sha256: str    # hash of the file contents, so a silently edited file is detected
    factors: pd.DataFrame


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_catalogue(path) -> Catalogue:
    path = Path(path)
    df = pd.read_csv(path)
    missing = set(FACTOR_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    if df["factor_id"].duplicated().any():
        raise ValueError(f"{path.name}: duplicate factor_id values")
    return Catalogue(path=path, version=path.stem, sha256=file_sha256(path), factors=df)


def load_gwp(path, gwp_set: str) -> dict:
    df = pd.read_csv(path)
    df = df[df["gwp_set"] == gwp_set]
    if df.empty:
        raise ValueError(f"GWP set {gwp_set!r} not found in {Path(path).name}")
    return dict(zip(df["gas"], df["value"]))
