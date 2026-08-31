from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor

from evaluate_physical_dem_candidate import (
    FEATURE_ORDER,
    NEW_COLUMNS,
    RF_PARAMS,
    engineer_features,
)


OFFSETS_M = (0, 400, 800, 1200, 1600)
COMPONENTS = (
    "persistence_score",
    "oof_response_score",
    "construction_exposure_score",
    "hydrogeological_susceptibility_score",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shifted_folds(frame: pd.DataFrame, offset_m: float) -> np.ndarray:
    gx = np.floor((frame["X"].to_numpy(float) - offset_m) / 2000.0).astype(int)
    gy = np.floor((frame["Y"].to_numpy(float) - offset_m) / 2000.0).astype(int)
    return ((gx + gy) % 5).astype(int)


def counterfactual(frame: pd.DataFrame) -> np.ndarray:
    result = frame[FEATURE_ORDER].copy()
    new_mask = frame[NEW_COLUMNS].fillna(0).sum(axis=1).to_numpy(float) > 0
    for year in range(2021, 2026):
        result[f"Cover_{year}"] = result["Cover_2020"]
        result[f"New_{year}"] = 0.0
        result[f"Vol_New_{year}"] = 0.0
    result["Load_Weighted"] = result["Cover_2020"].fillna(0) * 5.0 / 10.0
    result.loc[new_mask, "Height_mean"] = 0.0
    result.loc[new_mask, "Load_3D_Weighted"] = 0.0
    return result.to_numpy(float)


def percentile_rank(values: pd.Series, eligible: pd.Series, zero_preserving: bool = False) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = eligible & values.notna() & np.isfinite(values.to_numpy(float))
    if zero_preserving:
        positive = valid & (values > 0)
        output.loc[valid & ~positive] = 0.0
        if positive.any():
            output.loc[positive] = values.loc[positive].rank(method="average", pct=True)
    elif valid.any():
        output.loc[valid] = values.loc[valid].rank(method="average", pct=True)
    return output.clip(0, 1)


def top_fraction_mask(values: pd.Series, eligible: pd.Series, fraction: float = 0.10) -> pd.Series:
    mask = pd.Series(False, index=values.index)
    valid = eligible & values.notna()
    if valid.any():
        threshold = values.loc[valid].quantile(1.0 - fraction)
        mask.loc[valid] = values.loc[valid] >= threshold
    return mask


def weight_schemes() -> dict[str, np.ndarray]:
    schemes = {"equal": np.repeat(0.25, 4)}
    for index, component in enumerate(COMPONENTS):
        weights = np.repeat(0.20, 4)
        weights[index] = 0.40
        schemes[f"emphasize_{component}"] = weights
    for index, component in enumerate(COMPONENTS):
        weights = np.repeat(0.30, 4)
        weights[index] = 0.10
        schemes[f"downweight_{component}"] = weights
    return schemes


def hydro_score(frame: pd.DataFrame, eligible: pd.Series) -> pd.Series:
    columns = ["Dist_Lake", "Dist_River", "Shallow_2021", "Deep_2021", "Z10_m", "Z063_m"]
    components = []
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.nunique(dropna=True) < 3:
            continue
        oriented = -values if column in {"Shallow_2021", "Deep_2021"} else values
        components.append(percentile_rank(oriented, eligible).rename(column))
    return pd.concat(components, axis=1).mean(axis=1, skipna=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--dem-column", required=True)
    parser.add_argument("--locked-folds", type=Path, required=True)
    parser.add_argument("--physical-artifact", type=Path, required=True)
    parser.add_argument("--physical-support-grid", type=Path, required=True)
    parser.add_argument("--old-artifact", type=Path, required=True)
    parser.add_argument("--old-priority-grid", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_excel(args.workbook)
    raw_old = engineer_features(raw)
    candidate = pd.read_csv(args.candidate_csv, usecols=["Grid_ID", args.dem_column])
    raw_physical = raw.merge(candidate, on="Grid_ID", how="left", validate="one_to_one")
    raw_physical["DEM"] = raw_physical[args.dem_column].where(
        raw_physical[args.dem_column].notna(), raw_physical["DEM"]
    )
    raw_physical = engineer_features(raw_physical)

    locked = pd.read_excel(args.locked_folds, usecols=["Grid_ID", "fold"])
    physical = raw_physical.loc[raw_physical["Settle_mean"].notna()].copy().reset_index(drop=True)
    old = raw_old.loc[raw_old["Settle_mean"].notna()].copy().reset_index(drop=True)
    physical = physical.merge(locked, on="Grid_ID", how="left", validate="one_to_one")
    old = old.merge(locked, on="Grid_ID", how="left", validate="one_to_one")
    if not np.array_equal(physical["Grid_ID"].to_numpy(), old["Grid_ID"].to_numpy()):
        raise RuntimeError("Old and physical modelled row order differs.")

    x = physical[FEATURE_ORDER].to_numpy(float)
    x_old = old[FEATURE_ORDER].to_numpy(float)
    y = -physical["Settle_mean"].to_numpy(float)
    cf = counterfactual(physical)
    construction = physical[NEW_COLUMNS].fillna(0).sum(axis=1).to_numpy(float) > 0

    physical_artifact = joblib.load(args.physical_artifact)
    physical_models = {int(item["fold"]) - 1: item["model"] for item in physical_artifact["folds"]}
    old_artifact = joblib.load(args.old_artifact)
    old_models = {int(item["fold"]) - 1: item["model"] for item in old_artifact["folds"]}
    locked_zero = physical["fold"].to_numpy(int) - 1
    if not np.array_equal(shifted_folds(physical, 0), locked_zero):
        raise RuntimeError("Offset-zero checkerboard does not match the locked fold workbook.")

    deltas: dict[int, np.ndarray] = {}
    predictions: dict[int, np.ndarray] = {}
    old_prediction = np.full(len(physical), np.nan)
    for fold in range(5):
        test = np.flatnonzero(locked_zero == fold)
        old_prediction[test] = old_models[fold].predict(x_old[test])

    for offset in OFFSETS_M:
        folds = shifted_folds(physical, offset)
        prediction = np.full(len(physical), np.nan)
        counterfactual_prediction = np.full(len(physical), np.nan)
        for fold in range(5):
            test = np.flatnonzero(folds == fold)
            train = np.flatnonzero(folds != fold)
            if offset == 0:
                model = physical_models[fold]
            else:
                model = RandomForestRegressor(**RF_PARAMS)
                sample_weight = np.where(y[train] > 10.0, 2.0, 1.0)
                model.fit(x[train], y[train], sample_weight=sample_weight)
            prediction[test] = model.predict(x[test])
            counterfactual_prediction[test] = model.predict(cf[test])
        predictions[offset] = prediction
        deltas[offset] = prediction - counterfactual_prediction
        print(
            json.dumps(
                {
                    "offset_m": offset,
                    "prediction_r2": float(1 - np.square(y - prediction).sum() / np.square(y - y.mean()).sum()),
                    "positive_delta_n": int((deltas[offset] > 0).sum()),
                }
            ),
            flush=True,
        )

    support = pd.read_csv(
        args.physical_support_grid,
        usecols=["Grid_ID", "physical_dem_within_support", "physical_dem_dissimilarity_ratio"],
    )
    support["physical_dem_within_support"] = support["physical_dem_within_support"].astype(bool)
    data = physical[[
        "Grid_ID", "X", "Y", *NEW_COLUMNS, "Cover_2020", "Cover_2025",
        "Dist_Lake", "Dist_River", "Shallow_2021", "Deep_2021", "Z10_m", "Z063_m",
    ]].copy()
    data["new_construction_mask"] = construction
    for offset in OFFSETS_M:
        data[f"offset_{offset}_delta"] = deltas[offset]
        data[f"offset_{offset}_positive"] = deltas[offset] > 0
    delta_columns = [f"offset_{offset}_delta" for offset in OFFSETS_M]
    data["positive_partition_count_0_to_5"] = data[
        [f"offset_{offset}_positive" for offset in OFFSETS_M]
    ].sum(axis=1).astype(int)
    response_magnitude = data[delta_columns].abs().mean(axis=1)
    data["oof_response_magnitude_mean"] = response_magnitude

    old_priority = pd.read_csv(args.old_priority_grid)
    data = data.merge(
        old_priority[["Grid_ID", "tc_cumulative_new_volume"]],
        on="Grid_ID",
        how="left",
        validate="one_to_one",
    )
    eligible = data["new_construction_mask"].astype(bool)
    data["persistence_score"] = data["positive_partition_count_0_to_5"].astype(float) / 5.0
    data.loc[~eligible, "persistence_score"] = np.nan
    data["oof_response_score"] = percentile_rank(response_magnitude, eligible, zero_preserving=True)
    data["construction_exposure_score"] = percentile_rank(
        data["tc_cumulative_new_volume"], eligible, zero_preserving=True
    )
    data["hydrogeological_susceptibility_score"] = hydro_score(data, eligible).where(eligible)

    component_matrix = data[list(COMPONENTS)].to_numpy(float)
    valid = eligible.to_numpy() & np.isfinite(component_matrix).all(axis=1)
    scheme_masks = []
    scheme_rows = []
    for name, weights in weight_schemes().items():
        score = np.full(len(data), np.nan)
        score[valid] = component_matrix[valid] @ weights
        data[f"priority_score_{name}"] = score
        top = top_fraction_mask(
            data[f"priority_score_{name}"],
            eligible & pd.Series(valid, index=data.index),
            fraction=0.10,
        )
        data[f"top10_{name}"] = top
        scheme_masks.append(top.to_numpy(float))
        scheme_rows.append(
            {
                "scheme": name,
                **{component: float(weight) for component, weight in zip(COMPONENTS, weights)},
                "top_decile_grid_count": int(top.sum()),
            }
        )
    data["priority_score"] = data["priority_score_equal"]
    data["priority_top10"] = data["top10_equal"]
    data["priority_top10_weight_robustness"] = np.mean(np.vstack(scheme_masks), axis=0)
    data.loc[~eligible, "priority_top10_weight_robustness"] = np.nan
    data = data.merge(support, on="Grid_ID", how="left", validate="one_to_one")
    data["physical_dem_tre_class"] = "Non-priority modelled grid"
    priority = data["priority_top10"].astype(bool)
    data.loc[priority & data["physical_dem_within_support"], "physical_dem_tre_class"] = (
        "Evidence-supported priority"
    )
    data.loc[priority & ~data["physical_dem_within_support"], "physical_dem_tre_class"] = (
        "Exploratory priority"
    )
    data["reconstruction_status"] = "RECONSTRUCTED_NOT_HISTORICAL_ORIGINAL"

    robust = data["priority_top10_weight_robustness"] >= 7 / 9
    data["action_level"] = ""
    data.loc[priority & data["physical_dem_within_support"] & robust, "action_level"] = "A1"
    data.loc[priority & data["physical_dem_within_support"] & ~robust, "action_level"] = "A2"
    data.loc[priority & ~data["physical_dem_within_support"] & robust, "action_level"] = "B1"
    data.loc[priority & ~data["physical_dem_within_support"] & ~robust, "action_level"] = "B2"

    output_path = args.output_dir / "physical_dem_monitoring_priority_grid_reconstructed.csv"
    data.to_csv(output_path, index=False, encoding="utf-8-sig", float_format="%.12g")
    action_columns = [
        "Grid_ID", "X", "Y", "priority_score", "priority_top10_weight_robustness",
        "physical_dem_within_support", "physical_dem_dissimilarity_ratio",
        "physical_dem_tre_class", "action_level", "positive_partition_count_0_to_5",
        "oof_response_magnitude_mean", "persistence_score", "oof_response_score",
        "construction_exposure_score", "hydrogeological_susceptibility_score",
        "reconstruction_status",
    ]
    action_path = args.output_dir / "D962_observation_candidates_reconstructed.csv"
    data.loc[priority, action_columns].sort_values(
        ["action_level", "priority_score"], ascending=[True, False]
    ).to_csv(action_path, index=False, encoding="utf-8-sig", float_format="%.12g")
    scheme_path = args.output_dir / "monitoring_priority_weight_sensitivity_reconstructed.csv"
    pd.DataFrame(scheme_rows).to_csv(scheme_path, index=False, encoding="utf-8-sig")

    old_top = old_priority["priority_top10"].astype(bool)
    old_ids = set(old_priority.loc[old_top, "Grid_ID"].astype(int))
    new_ids = set(data.loc[priority, "Grid_ID"].astype(int))
    old_robust_ids = set(
        old_priority.loc[old_priority["priority_top10_weight_robustness"] >= 7 / 9, "Grid_ID"].astype(int)
    )
    new_robust_ids = set(data.loc[robust, "Grid_ID"].astype(int))
    evidence = int((priority & data["physical_dem_within_support"]).sum())
    exploratory = int((priority & ~data["physical_dem_within_support"]).sum())
    physical_prediction = predictions[0]
    report = {
        "status": "PASS_EXACT_ARCHIVED_PRIORITY_REPRODUCTION",
        "scientific_boundary": (
            "This is a deterministic V15 reconstruction from the documented source DEM, locked folds, "
            "archived method and recovered input workbook. It is not the lost historical byte-identical CSV."
        ),
        "rows": int(len(data)),
        "eligible_construction_n": int(eligible.sum()),
        "priority_n": int(priority.sum()),
        "evidence_supported_priority_n": evidence,
        "exploratory_priority_n": exploratory,
        "robust_priority_n": int(robust.sum()),
        "priority_changed_membership_n": int(len(old_ids ^ new_ids)),
        "priority_jaccard_old_vs_physical": float(len(old_ids & new_ids) / len(old_ids | new_ids)),
        "robust_priority_jaccard_old_vs_physical": float(
            len(old_robust_ids & new_robust_ids) / len(old_robust_ids | new_robust_ids)
        ),
        "prediction_spearman_old_vs_physical": float(spearmanr(old_prediction, physical_prediction)[0]),
        "archived_gate": {
            "priority_n_expected": 1810,
            "supported_expected": 1469,
            "exploratory_expected": 341,
            "robust_expected": 1574,
            "changed_membership_expected": 428,
            "priority_jaccard_expected": 0.7885375494071146,
            "robust_jaccard_expected": 0.786117381489842,
            "prediction_spearman_expected": 0.9934384436632011,
        },
        "inputs": {
            args.workbook.name: sha256(args.workbook),
            args.candidate_csv.name: sha256(args.candidate_csv),
            args.locked_folds.name: sha256(args.locked_folds),
            args.physical_artifact.name: sha256(args.physical_artifact),
            args.physical_support_grid.name: sha256(args.physical_support_grid),
            args.old_artifact.name: sha256(args.old_artifact),
            args.old_priority_grid.name: sha256(args.old_priority_grid),
        },
        "outputs": {
            output_path.name: sha256(output_path),
            action_path.name: sha256(action_path),
            scheme_path.name: sha256(scheme_path),
        },
    }
    exact = (
        report["priority_n"] == 1810
        and evidence == 1469
        and exploratory == 341
        and report["robust_priority_n"] == 1574
        and report["priority_changed_membership_n"] == 428
        and abs(report["priority_jaccard_old_vs_physical"] - 0.7885375494071146) <= 1e-15
        and abs(report["robust_priority_jaccard_old_vs_physical"] - 0.786117381489842) <= 1e-15
        and abs(report["prediction_spearman_old_vs_physical"] - 0.9934384436632011) <= 1e-15
    )
    report["status"] = (
        "PASS_EXACT_ARCHIVED_PRIORITY_REPRODUCTION"
        if exact
        else "FAIL_ARCHIVED_PRIORITY_REPRODUCTION"
    )
    report_path = args.output_dir / "physical_dem_priority_reconstruction_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
