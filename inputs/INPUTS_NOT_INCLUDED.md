# Controlled inputs not included in the public code release

This directory is intentionally empty.  The frozen audit entry point expects the following controlled files only after the data providers, institutions, and all co-authors have authorised access and use:

| Relative location expected by scripts | Purpose | Public release status |
|---|---|---|
| `inputs/physical_dem_candidates_48470.csv` | Frozen physical-DEM candidate subset | Not released; grid-level data. |
| `inputs/journal_spatial_folds_locked.xlsx` | Locked spatial-fold definition | Not released; contains grid-level spatial information. |
| `inputs/frozen_xiongan_tre_ensemble.joblib` | Frozen fitted model artefact | Not released; model and input-rights review required. |
| `inputs/monitoring_priority_evidence_grid.csv` | Priority/support grid | Not released; contains location-level candidate information. |
| `reference_outputs/locked_fold_grid_comparison_reconstructed.csv` | Grid-level frozen comparison output | Not released; contains grid-level output. |
| Author-supplied `Building_Timeline.xlsx` | Original modelling workbook | Not released; contains controlled, third-party-derived fields. |

The audit recognises two retained byte-level hashes of the controlled workbook: `fb63dab0f66a44aa823cb02455a3f26438d98c9b2c220aa64fe8f97e977b03ab` and `f1758236b426b984373f974d88bd052504c23dbf6626a236d1c272b7002cf70a`. Both copies reproduce the locked reference predictions within the stated `1e-9` tolerance. The audit report records which copy was supplied.

No reader should request, infer, reconstruct, or redistribute these materials from this package.  Any access request must be directed to the corresponding author and assessed against source licences, institutional rules, and the rights of all contributors.
