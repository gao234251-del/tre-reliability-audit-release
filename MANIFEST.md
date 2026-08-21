# Public-code release manifest

Package: `TRE reconstruction and audit scripts`  
Version: `0.1.1`  
Status: public audit and reconstruction subset.

## Included files

| Path | Role | Release status |
|---|---|---|
| `code/evaluate_physical_dem_candidate_v15.py` | Physical-DEM sensitivity reconstruction | Public code release |
| `code/reconstruct_physical_dem_priority_v15.py` | Priority reconstruction under the physical-DEM sensitivity analysis | Public code release |
| `code/verify_frozen_baseline.py` | Frozen-baseline verification logic | Public code release |
| `code/verify_reference_bundle.py` | SHA-256 checker for controlled local files | Public code release |
| `scripts/run_frozen_audit.ps1` | Optional audit entry point after lawful controlled-input access | Public code release |
| `requirements.txt` | Archived Python dependencies | Public code release |
| `reference_outputs/*` | Small aggregate reconstruction summaries only | Public derived data release (CC BY 4.0; see `LICENSE-DATA`) |
| `inputs/INPUTS_NOT_INCLUDED.md` | Controlled-input inventory and access boundary | Public release |
| `README.md`, `CITATION.cff`, `SECURITY.txt`, `LICENSE-DATA` | Documentation, citation, security and data-licensing guidance | Public release |

## Deliberately excluded

No raw Sentinel-1 scenes, SARscape projects or logs, `Building_Timeline.xlsx`, spatial-fold/grid inputs, candidate coordinates, model artefacts, grid-level predicted outputs, account files, or third-party source data are included.  This release is therefore not a standalone end-to-end reproduction archive.

## Release controls

The MIT License applies only to author-written code in `code/` and `scripts/`.  The public derived outputs in `reference_outputs/` are released under CC BY 4.0; see `LICENSE-DATA` and the associated [Zenodo record](https://doi.org/10.5281/zenodo.22048331).  Controlled data, grid-level outputs, model artefacts, and third-party materials remain excluded.
