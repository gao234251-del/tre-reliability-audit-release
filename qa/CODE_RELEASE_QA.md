# Code-release QA

Date: 2026-08-21  
Package status: `0.1.1` — public audit and reconstruction subset.

## Scope audit

- Included: four author-written Python scripts, one PowerShell audit launcher, a dependency file, and four small aggregate reference outputs.
- Excluded: raw satellite data, SARscape projects/logs, the controlled modelling workbook, coordinate/grid-level inputs and outputs, monitoring candidate locations, frozen model artefacts, cache files, and third-party source datasets.
- Interpretation: the package supports inspection and reconstruction of selected frozen analyses.  It does not by itself reproduce the full InSAR-to-TRE workflow.

## Automated static checks performed

1. Parsed all four included Python scripts with the archived local Python interpreter without executing a model fit: pass.
2. Parsed the PowerShell launcher without execution: pass.
3. Scanned included text/code for common credential patterns: no secret-like value was found.  The sole keyword hit was the explanatory word `credential` in `SECURITY.txt`.
4. Scanned Python/PowerShell files for Windows and common Unix absolute-path strings: no match.
5. Checked cache artefacts: zero `__pycache__` directories and zero `.pyc` files.

## Release controls

The package is released under the MIT License and remains limited to the audited scope described above. Controlled inputs, grid-level outputs, model artefacts, and third-party source materials are excluded.
