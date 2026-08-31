from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from evaluate_physical_dem_candidate import FEATURE_ORDER, engineer_features


EXPECTED_WORKBOOK_HASHES = {
    "fb63dab0f66a44aa823cb02455a3f26438d98c9b2c220aa64fe8f97e977b03ab",
    "f1758236b426b984373f974d88bd052504c23dbf6626a236d1c272b7002cf70a",
}

EXPECTED_HASHES = {
    "candidate_csv": "61d9e913804b3caafbda71273ee0a73bf8ed8f281892db1e3424781214ea7d93",
    "locked_folds": "38260947dd53a654feb4951f4aa2372490e197f80ed64f0b921a0031fd531f25",
    "old_artifact": "7f8e40809c4f4963f1e5510e09110b6e4843c9f8a8a3941cf82fa86376efdba3",
    "reference_grid": "4db20c29aab155c3162114d945f5882f47ebe1e0753cf3654e863e9662cf64c4",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the archived frozen Xiong'an baseline model against the locked reference grid."
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--locked-folds", type=Path, required=True)
    parser.add_argument("--old-artifact", type=Path, required=True)
    parser.add_argument("--reference-grid", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    supplied = {
        "workbook": args.workbook,
        "candidate_csv": args.candidate_csv,
        "locked_folds": args.locked_folds,
        "old_artifact": args.old_artifact,
        "reference_grid": args.reference_grid,
    }
    hashes = {name: sha256(path) for name, path in supplied.items()}
    hash_gate = {
        name: (
            hashes[name] in EXPECTED_WORKBOOK_HASHES
            if name == "workbook"
            else hashes[name] == EXPECTED_HASHES[name]
        )
        for name in hashes
    }

    raw = pd.read_excel(args.workbook)
    candidates = pd.read_csv(args.candidate_csv, usecols=["Grid_ID", "DEM_physical_average"])
    raw = raw.merge(candidates, on="Grid_ID", how="left", validate="one_to_one")
    raw["DEM"] = raw["DEM_physical_average"].where(raw["DEM_physical_average"].notna(), raw["DEM"])
    modelled = engineer_features(raw).loc[lambda frame: frame["Settle_mean"].notna()].copy()
    locked = pd.read_excel(args.locked_folds, usecols=["Grid_ID", "fold"])
    modelled = modelled.merge(locked, on="Grid_ID", how="left", validate="one_to_one")
    if modelled["fold"].isna().any():
        raise RuntimeError("Locked fold mapping is incomplete.")

    x = modelled[FEATURE_ORDER].to_numpy(float)
    folds = modelled["fold"].to_numpy(int)
    artifact = joblib.load(args.old_artifact)
    prediction = np.full(len(modelled), np.nan)
    for item in artifact["folds"]:
        test_index = np.flatnonzero(folds == int(item["fold"]))
        prediction[test_index] = item["model"].predict(x[test_index])

    observed = pd.DataFrame({"Grid_ID": modelled["Grid_ID"].to_numpy(), "prediction": prediction})
    reference = pd.read_csv(
        args.reference_grid,
        usecols=["Grid_ID", "old_dn_oof_prediction_mm_yr"],
    )
    comparison = observed.merge(reference, on="Grid_ID", how="inner", validate="one_to_one")
    if len(comparison) != len(observed):
        raise RuntimeError("Reference grid does not contain every modelled Grid_ID.")
    absolute_error = np.abs(
        comparison["prediction"].to_numpy(float)
        - comparison["old_dn_oof_prediction_mm_yr"].to_numpy(float)
    )
    exact = bool(np.allclose(absolute_error, 0.0, rtol=0.0, atol=1e-9))
    report = {
        "status": "PASS_FROZEN_BASELINE_AUDIT" if all(hash_gate.values()) and exact else "FAIL_FROZEN_BASELINE_AUDIT",
        "scientific_boundary": "This audit verifies the archived frozen-model inference only. It does not reproduce Sentinel/SBAS preprocessing and does not establish causality or engineering-risk grade.",
        "modelled_rows": int(len(modelled)),
        "max_abs_difference_mm_yr": float(absolute_error.max()),
        "mean_abs_difference_mm_yr": float(absolute_error.mean()),
        "within_1e-9": exact,
        "input_hashes": hashes,
        "accepted_workbook_hashes": sorted(EXPECTED_WORKBOOK_HASHES),
        "hash_gate": hash_gate,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
