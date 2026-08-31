from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "inputs/physical_dem_candidates_48470.csv": "61d9e913804b3caafbda71273ee0a73bf8ed8f281892db1e3424781214ea7d93",
    "inputs/journal_spatial_folds_locked.xlsx": "38260947dd53a654feb4951f4aa2372490e197f80ed64f0b921a0031fd531f25",
    "inputs/frozen_xiongan_tre_ensemble.joblib": "7f8e40809c4f4963f1e5510e09110b6e4843c9f8a8a3941cf82fa86376efdba3",
    "inputs/monitoring_priority_evidence_grid.csv": "9d8a32bd2332773bf5fe0861553e3b8cabc38bed2d852a0828752db79fac9a3e",
    "reference_outputs/locked_fold_grid_comparison_reconstructed.csv": "4db20c29aab155c3162114d945f5882f47ebe1e0753cf3654e863e9662cf64c4",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check static files in the D962 model reproduction package.")
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()
    root = args.package_root.resolve()
    audit = {}
    for relative, expected in EXPECTED.items():
        path = root / relative
        actual = sha256(path) if path.exists() else None
        audit[relative] = {"exists": path.exists(), "sha256": actual, "matches": actual == expected}
    result = {
        "status": "PASS_STATIC_FILE_AUDIT" if all(item["matches"] for item in audit.values()) else "FAIL_STATIC_FILE_AUDIT",
        "files": audit,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
