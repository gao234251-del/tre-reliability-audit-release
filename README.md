# TRE reconstruction and audit scripts — public release

Version: `0.1.1`  
Status: public audit and reconstruction subset.

## Purpose and scope

This package contains the author-written scripts used to audit and reconstruct selected frozen outputs reported in the accompanying manuscript on the transfer-reliability envelope (TRE).  It supports inspection of the locked modelling configuration, a physical-DEM sensitivity reconstruction, and selected priority-reconstruction checks.

It is intentionally a **selected reconstruction subset**, not an end-to-end reproduction package for Sentinel-1 download, SARscape/SBAS processing, interferogram-network construction, geocoding, or the complete manuscript analysis.  The frozen GeoAI workflow was instantiated with a weighted random forest; the scripts are not released as an independently validated prediction service.

## Included

- `code/`: four Python reconstruction and audit scripts.
- `scripts/run_frozen_audit.ps1`: an optional PowerShell entry point for the frozen-model audit once controlled inputs have been supplied lawfully.
- `reference_outputs/`: four small, aggregate reconstruction summaries; no raw scenes, 100 m grid coordinates, candidate locations, or model artefacts are included.
- `requirements.txt`: the archived Python package versions.
- `inputs/INPUTS_NOT_INCLUDED.md`: the controlled input inventory and request boundary.

## Not included

The following are deliberately absent: Sentinel-1 source products; SARscape projects and execution logs; `Building_Timeline.xlsx`; locked folds or any coordinate/grid-level input; monitoring candidate locations; fitted model artefacts; and third-party hydrogeological, construction, terrain, or map data.  Their availability and redistribution depend on provider, institutional, and third-party rights.

Consequently, the repository alone cannot execute `run_frozen_audit.ps1`.  It becomes executable only for an authorised user who has obtained the controlled inputs stated in `inputs/INPUTS_NOT_INCLUDED.md`, retained their provenance, and has permission to use them.

## Environment

The archived environment was Windows with Python 3.9.12.  Install the packages listed in `requirements.txt` into a separate environment.  Exact historical package pinning improves comparability but does not substitute for a clean-machine end-to-end rerun.

## Integrity check after authorised input access

The script `code/verify_reference_bundle.py` stores SHA-256 hashes for five controlled files.  After obtaining authorised local copies, place them in the relative locations documented in `inputs/INPUTS_NOT_INCLUDED.md` and run:

```powershell
python code/verify_reference_bundle.py --package-root . --output-json qa/static_file_audit.json
```

Only then may an authorised user run `scripts/run_frozen_audit.ps1 -Workbook <path-to-authorised-Building_Timeline.xlsx>`.

## Citation and licence

Use `CITATION.cff` when citing this code package.  This release is distributed under the MIT License; see `LICENSE`.
