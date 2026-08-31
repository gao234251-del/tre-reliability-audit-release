# Code-release QA

Date: 2026-08-31

Package status: `0.1.3` — public audit and reconstruction subset.

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
6. Scanned tracked filenames and text for internal analysis-iteration labels: no match; public files use descriptive, revision-independent names.
7. Ran the frozen-baseline audit separately with both retained workbook hashes: both passed the input hash gate and reproduced all 48,470 locked reference predictions within the `1e-9` tolerance.

## Release controls

The MIT License applies only to author-written code in `code/` and `scripts/`. The small public derived outputs in `reference_outputs/` are released under CC BY 4.0; see `LICENSE-DATA`. The broader public archive of non-restricted aggregate and fold-level derived tables is available through the [Zenodo concept DOI](https://doi.org/10.5281/zenodo.22048331), also under CC BY 4.0. Controlled inputs, grid-level outputs, model artefacts, and third-party source materials are excluded.
