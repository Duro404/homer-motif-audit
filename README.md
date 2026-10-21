# HOMER Motif Audit — GitHub preview (v0.3.0-rc2)

**Owner-review release candidate only. No public repository has been created or authorized for upload by this package.**

A small, offline, Python-standard-library command-line tool for **auditable, provisional HOMER motif-name annotations** and **restricted TF-name to JASPAR 2026 class/family metadata crosswalks**.

**This is not a PWM alignment, motif de-duplication, TF occupancy, binding validation, or a novel biological TF-family classifier.** Even a supported TF-name match does not establish that the HOMER and JASPAR models share a PWM. User-supplied reference labels are not independently authenticated.

## Requirements

- Python 3.10 or later (runtime requires only the standard library; other versions not yet validated for this preview).
- A HOMER `knownResults.txt` file or a tab-separated table containing motif names.
- HOMER itself and internet access are **not required** to annotate an existing file.

## Quick start

From the project directory:

```bash
python3 -B -m homer_audit.cli annotate \
  --input examples/synthetic_knownResults.txt \
  --input-format homer-known \
  --outdir demo-output \
  --summary --q-threshold 0.05
```

Choose a fresh output directory. The CLI refuses to replace existing output files unless you explicitly pass `--overwrite`.

General TSV example:

```bash
python3 -B -m homer_audit.cli annotate \
  --input examples/synthetic_motifs.tsv \
  --input-format generic-tsv \
  --outdir demo-generic-output \
  --summary --group-by set,tissue
```

For a real HOMER output, use `--input /path/to/knownResults.txt` with `--input-format homer-known`. A default `q < 0.05` threshold applies to **summaries only**; the program does not recalculate P/q values.

## Inputs

| Item | Required | Meaning |
| --- | --- | --- |
| HOMER `knownResults.txt` or generic TSV | Yes | Motif names; q-value column needed for `--summary` |
| `--rules` TSV | No | Overrides shipped **provisional** name-pattern rules |
| `--curated` TSV | No | User overrides, treated as requiring review |
| `--reference-table` TSV | No | Offline user reference comparison; validity NOT independently confirmed |

The built-in mapping file `homer_audit/reference_name_rules_v04.tsv` is a **restricted, frozen name-metadata lookup**, containing exactly 10 narrowly defined rules and exact TF symbol allowlists. It is not the complete JASPAR database. It should not be generalized to unlisted TF names.

## Outputs

| Output | Purpose |
| --- | --- |
| `annotated.tsv` | Preserves input columns, appends name, provisional label, reference, risk and scientific-claim fields |
| `summary.tsv` | **Legacy provisional** `family_label` counts for significant motif records |
| `summary_evidence.tsv` | Evidence-scope, label-level and review-action grouped counts |
| `summary_restricted_name_metadata.tsv` | Significant records with restricted TF-name metadata support; **not PWM validation** |
| `audit.json` | Input/rules/reference SHA256s, software version, counters and interpretation caveats |
| `reference_comparison.tsv` | Optional: comparison with a user-supplied reference table |

In `annotated.tsv`, `family_label` is **a provisional legacy display field**. Prefer `v03_label_level`, `v03_claim_disposition`, `v03_metadata_evidence_scope`, `v03_review_action`, `v03_reference_name_supported`, and the original `v03_reference_tf_class`/`v03_reference_tf_family` fields for interpretation. `v03_family_claim_validated` is always `FALSE`. A record with `v03_review_required=FALSE` is **not** biologically approved.

### Special cases

Generic `ETS`, `AP-1`, `NFY` and held member exceptions (including BATF), compound/dimer names, and fusion/chimeric labels receive conservative review/claim dispositions. CTCF is a TF symbol, but its name alone does not prove binding.

## Testing

```bash
python3 -B -m unittest discover -s tests -q
```

The independently published source-table software regression test is optional and uses **user-supplied local copies** of three public, Git-blob-pinned HOMER tables. It does not fetch data:

```bash
python3 -B scripts/validate_public_homer_offline.py \
  --source-dir /path/to/public_sources \
  --outdir /path/to/new_integration_output
```

See [validation scope and source links](docs/VALIDATION.md) and [scientific limitations](docs/SCIENCE_SCOPE.md).

## Similar tools and scope

HOMER already performs enrichment analysis; GimmeMotifs, MEME Suite Tomtom, and RSAT matrix-clustering perform motif comparisons and/or clustering. This tool instead focuses on **auditing downstream textual name labels and metadata provenance**, without running PWM comparisons. It is not a substitute for those packages.

## License, attribution and publication status

The author has declared independent authorship of this source code and has chosen the MIT License for the original software. The root [`LICENSE`](LICENSE) contains the author's selected public copyright holder identification. This declaration is not an independent legal verification of authorship.

The adapted JASPAR 2026 reference-name crosswalk is separately attributed in [NOTICE-JASPAR.md](NOTICE-JASPAR.md) under the upstream CC BY 4.0 terms. Code licensing does not override upstream database attribution. See [release checklist](docs/RELEASE_CHECKLIST.md) and [license decision](docs/LICENSE_DECISION.md).

**Not yet approved for a public GitHub upload.** The MIT license has been generated, but final inspection, clean Git staging/history review, and explicit owner release approval remain outstanding. This tree contains no intentionally bundled experimental data, server automation, downloaded public HOMER results or internal comparison code.
