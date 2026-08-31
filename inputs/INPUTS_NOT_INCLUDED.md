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

No reader should request, infer, reconstruct, or redistribute these materials from this package.  Any access request must be directed to the corresponding author and assessed against source licences, institutional rules, and the rights of all contributors.
