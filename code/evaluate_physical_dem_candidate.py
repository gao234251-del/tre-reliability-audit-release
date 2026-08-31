from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


FEATURE_ORDER = [
    *[f"Cover_{year}" for year in range(2020, 2026)],
    *[f"New_{year}" for year in range(2021, 2026)],
    "Load_Weighted",
    "Height_mean",
    "Load_3D_Weighted",
    *[f"Vol_New_{year}" for year in range(2021, 2026)],
    "DEM",
    "Dist_Lake",
    "Z10_m",
    "Z063_m",
    *[f"LC_{value}" for value in (0, 10, 20, 30, 40, 50, 60, 80, 90)],
    "Dist_River_m",
    "River_Present",
    "Shallow_2021",
    "Deep_2021",
]
NEW_COLUMNS = [f"New_{year}" for year in range(2021, 2026)]
RF_PARAMS = {
    "n_estimators": 500,
    "max_features": "sqrt",
    "min_samples_leaf": 5,
    "max_depth": 15,
    "random_state": 42,
    "n_jobs": -1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    cover = [f"Cover_{year}" for year in range(2020, 2026)]
    new = NEW_COLUMNS
    building = frame[cover + new].fillna(0).sum(axis=1) > 0
    valid = building & (frame["Height_mean"].fillna(0) > 0)
    missing = building & (frame["Height_mean"].fillna(0) <= 0)
    if missing.any():
        tree = cKDTree(frame.loc[valid, ["X", "Y"]].to_numpy(float))
        distances, indices = tree.query(
            frame.loc[missing, ["X", "Y"]].to_numpy(float),
            k=min(5, int(valid.sum())),
        )
        values = frame.loc[valid, "Height_mean"].to_numpy(float)
        weights = 1.0 / np.maximum(distances, 1e-6)
        frame.loc[missing, "Height_mean"] = (
            (weights * values[indices]).sum(axis=1) / weights.sum(axis=1)
        )
    frame["Load_Weighted"] = (
        5.0 * frame["Cover_2020"].fillna(0)
        + sum(frame[column].fillna(0) for column in new)
    ) / 10.0
    for year in range(2021, 2026):
        frame[f"Vol_New_{year}"] = (
            frame[f"New_{year}"].fillna(0) * frame["Height_mean"].fillna(0)
        )
    frame["Load_3D_Weighted"] = frame["Load_Weighted"] * frame["Height_mean"].fillna(0)
    landcover = frame["landcover"].fillna(-999).astype(str)
    for value in (0, 10, 20, 30, 40, 50, 60, 80, 90):
        frame[f"LC_{value}"] = (landcover == str(value)).astype(np.int8)
    frame["Dist_River_m"] = frame["Dist_River"]
    frame["River_Present"] = (frame["Dist_River"].fillna(np.inf) <= 1.0).astype(np.int8)
    return frame


def weighted_space(x_train: np.ndarray, x_query: np.ndarray, importance: np.ndarray):
    center = np.nanmean(x_train, axis=0)
    scale = np.nanstd(x_train, axis=0)
    scale[~np.isfinite(scale) | (scale < 1e-12)] = 1.0
    weights = np.asarray(importance, dtype=float).clip(min=0)
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = np.ones(x_train.shape[1], dtype=float)
    weights = weights / weights.sum()
    multiplier = np.sqrt(weights * x_train.shape[1])
    return (
        (x_train - center) / scale * multiplier,
        (x_query - center) / scale * multiplier,
        center,
        scale,
        multiplier,
    )


def calibration_threshold(z_train: np.ndarray, training_folds: np.ndarray, rng):
    distances = []
    for fold in np.unique(training_folds):
        query = np.flatnonzero(training_folds == fold)
        if len(query) > 1500:
            query = rng.choice(query, size=1500, replace=False)
        reference = np.flatnonzero(training_folds != fold)
        distance = cKDTree(z_train[reference]).query(z_train[query], k=1)[0]
        distances.append(distance)
    pooled = np.concatenate(distances)
    return float(np.quantile(pooled, 0.95)), pooled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--dem-column", required=True)
    parser.add_argument("--locked-folds", type=Path, required=True)
    parser.add_argument("--old-artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_excel(args.workbook)
    candidate = pd.read_csv(args.candidate_csv, usecols=["Grid_ID", args.dem_column])
    raw = raw.merge(candidate, on="Grid_ID", how="left", validate="one_to_one")
    raw["DEM"] = raw[args.dem_column].where(raw[args.dem_column].notna(), raw["DEM"])
    raw = engineer_features(raw)
    modelled = raw.loc[raw["Settle_mean"].notna()].copy().reset_index(drop=True)
    locked = pd.read_excel(args.locked_folds, usecols=["Grid_ID", "fold"])
    modelled = modelled.merge(locked, on="Grid_ID", how="left", validate="one_to_one")
    if modelled["fold"].isna().any():
        raise RuntimeError("Locked fold mapping is incomplete.")

    x = modelled[FEATURE_ORDER].to_numpy(float)
    y = -modelled["Settle_mean"].to_numpy(float)
    folds = modelled["fold"].to_numpy(int)
    prediction = np.full(len(modelled), np.nan)
    distance = np.full(len(modelled), np.nan)
    threshold = np.full(len(modelled), np.nan)
    physical_folds = []
    fold_rows = []
    rng = np.random.default_rng(42)

    for outer_fold in range(1, 6):
        test_index = np.flatnonzero(folds == outer_fold)
        train_index = np.flatnonzero(folds != outer_fold)
        model = RandomForestRegressor(**RF_PARAMS)
        sample_weight = np.where(y[train_index] > 10.0, 2.0, 1.0)
        model.fit(x[train_index], y[train_index], sample_weight=sample_weight)
        prediction[test_index] = model.predict(x[test_index])
        z_train, z_test, center, scale, multiplier = weighted_space(
            x[train_index], x[test_index], model.feature_importances_
        )
        fold_threshold, calibration_distances = calibration_threshold(
            z_train, folds[train_index], rng
        )
        test_distance = cKDTree(z_train).query(z_test, k=1)[0]
        distance[test_index] = test_distance
        threshold[test_index] = fold_threshold
        supported = test_distance <= fold_threshold
        fold_rows.append(
            {
                "fold": outer_fold,
                "training_n": int(len(train_index)),
                "test_n": int(len(test_index)),
                "calibration_n": int(len(calibration_distances)),
                "support_threshold": fold_threshold,
                "supported_n": int(supported.sum()),
                "supported_percent": float(100 * supported.mean()),
                "fold_r2": float(r2_score(y[test_index], prediction[test_index])),
                "fold_rmse_mm_yr": float(mean_squared_error(y[test_index], prediction[test_index], squared=False)),
            }
        )
        physical_folds.append(
            {
                "fold": outer_fold,
                "model": model,
                "center": center,
                "scale": scale,
                "multiplier": multiplier,
                "train_z": z_train,
                "support_threshold": fold_threshold,
                "training_n": int(len(train_index)),
                "test_n": int(len(test_index)),
                "calibration_n": int(len(calibration_distances)),
                "feature_importances": model.feature_importances_,
            }
        )

    ratio = distance / threshold
    supported = ratio <= 1.0
    construction = modelled[NEW_COLUMNS].fillna(0).sum(axis=1).to_numpy(float) > 0
    old_artifact = joblib.load(args.old_artifact)
    old_prediction = np.full(len(modelled), np.nan)
    for fold in old_artifact["folds"]:
        test_index = np.flatnonzero(folds == int(fold["fold"]))
        old_prediction[test_index] = fold["model"].predict(x[test_index])

    output = pd.DataFrame(
        {
            "Grid_ID": modelled["Grid_ID"].to_numpy(),
            "X": modelled["X"].to_numpy(float),
            "Y": modelled["Y"].to_numpy(float),
            "fold": folds,
            "y_true": y,
            "old_dn_oof_prediction_mm_yr": old_prediction,
            "physical_dem_oof_prediction_mm_yr": prediction,
            "physical_dem_oof_residual": y - prediction,
            "physical_dem_absolute_oof_error": np.abs(y - prediction),
            "physical_dem_support_distance": distance,
            "physical_dem_support_threshold": threshold,
            "physical_dem_dissimilarity_ratio": ratio,
            "physical_dem_within_support": supported,
            "construction_mask": construction,
            "physical_dem_m": modelled["DEM"].to_numpy(float),
        }
    )
    grid_path = args.output_dir / "locked_fold_grid_comparison_reconstructed.csv"
    output.to_csv(grid_path, index=False, encoding="utf-8-sig", float_format="%.12g")
    fold_path = args.output_dir / "physical_dem_fold_metrics_reconstructed.csv"
    pd.DataFrame(fold_rows).to_csv(fold_path, index=False, encoding="utf-8-sig", float_format="%.12g")

    artifact = {
        "metadata": {
            "artifact": "Reconstructed Xiong'an physical-DEM five-fold TRE ensemble",
            "version": "V15_RECONSTRUCTED_2026-08-15",
            "status": "RECONSTRUCTED_NOT_HISTORICAL_ORIGINAL",
            "feature_order": FEATURE_ORDER,
            "target": "Subsidence_Tendency = -Settle_mean; positive = stronger subsidence",
            "rf_params": RF_PARAMS,
            "locked_folds_sha256": sha256(args.locked_folds),
            "source_workbook_sha256": sha256(args.workbook),
            "source_candidate_sha256": sha256(args.candidate_csv),
            "dem_column": args.dem_column,
        },
        "folds": physical_folds,
    }
    artifact_path = args.output_dir / "frozen_xiongan_physical_dem_tre_ensemble_reconstructed.joblib"
    joblib.dump(artifact, artifact_path, compress=0)

    metrics = {
        "status": "RECONSTRUCTED_CANDIDATE_AWAITING_ARCHIVED_METRIC_GATE",
        "dem_column": args.dem_column,
        "rows": int(len(output)),
        "oof_r2": float(r2_score(y, prediction)),
        "oof_rmse_mm_yr": float(mean_squared_error(y, prediction, squared=False)),
        "oof_mae_mm_yr": float(mean_absolute_error(y, prediction)),
        "prediction_spearman": float(pd.Series(old_prediction).corr(pd.Series(prediction), method="spearman")),
        "supported_all_n": int(supported.sum()),
        "supported_all_percent": float(100 * supported.mean()),
        "construction_n": int(construction.sum()),
        "supported_construction_n": int(np.sum(supported & construction)),
        "supported_construction_percent": float(100 * supported[construction].mean()),
        "archived_metric_gate": {
            "expected_oof_r2": 0.77500326757226,
            "expected_supported_all_n": 47127,
            "expected_supported_construction_n": 17110,
            "r2_absolute_gap": float(abs(r2_score(y, prediction) - 0.77500326757226)),
            "supported_all_gap": int(supported.sum() - 47127),
            "supported_construction_gap": int(np.sum(supported & construction) - 17110),
        },
        "outputs": {
            grid_path.name: sha256(grid_path),
            fold_path.name: sha256(fold_path),
            artifact_path.name: sha256(artifact_path),
        },
    }
    passed = (
        metrics["archived_metric_gate"]["r2_absolute_gap"] <= 1e-12
        and metrics["archived_metric_gate"]["supported_all_gap"] == 0
        and metrics["archived_metric_gate"]["supported_construction_gap"] == 0
    )
    metrics["status"] = "PASS_EXACT_ARCHIVED_METRIC_REPRODUCTION" if passed else "FAIL_ARCHIVED_METRIC_REPRODUCTION"
    report_path = args.output_dir / "physical_dem_candidate_reconstruction_report.json"
    report_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
