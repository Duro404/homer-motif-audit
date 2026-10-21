# HOMER Motif Audit

**Auditable, conservative HOMER motif-name annotation and restricted TF-name-to-JASPAR 2026 metadata crosswalk**  
Version: **v0.3.0-rc2** (release candidate)

HOMER Motif Audit is a small, offline Python command-line utility for interpreting **existing** HOMER known-motif enrichment result tables. It preserves the input records, derives provisional reporting labels from documented name rules, attaches a limited JASPAR 2026 TF-name/class/family crosswalk for explicitly allowed TF symbols, flags ambiguous cases for review, and records provenance and interpretation limits.

**Scope:** This is *textual motif-name annotation*, **not** PWM/PFM alignment, motif discovery, sequence-based motif classification, motif de-duplication, TF occupancy determination, proof of direct binding, or independent biological validation. Reference metadata associated with a TF name must not be interpreted as evidence that a HOMER motif and a JASPAR motif have identical binding matrices.

## Requirements

- Python **3.10+**; the runtime uses only Python's standard library. GitHub Actions tests Python 3.10 and 3.12.
- A HOMER `knownResults.txt` or tab-separated table containing a motif-name column. For significance summaries, a numeric q-value column is required.
- No installed HOMER executable, internet connection, or JASPAR download is required **for annotation of an existing table**.

## Quick start

Run in the project root (on Windows, use `python` instead of `python3` if appropriate):

```bash
python -B -m homer_audit.cli annotate \
  --input examples/synthetic_knownResults.txt \
  --input-format homer-known \
  --outdir demo-output \
  --summary --q-threshold 0.05
```

Generic tabular input with optional grouping:

```bash
python -B -m homer_audit.cli annotate \
  --input examples/synthetic_motifs.tsv \
  --input-format generic-tsv \
  --outdir demo-generic-output \
  --summary --group-by set,tissue
```

> **Windows PowerShell:** the examples above use Unix-style `\` line continuation. Paste each command as one line in PowerShell, or use its backtick continuation character. The `examples/` data are synthetic.

The CLI accepts `--input-format auto` (default), `homer-known`, or `generic-tsv`, and optional `--motif-column` and `--q-column` overrides. Use a new `--outdir` each time; existing output files are not replaced unless `--overwrite` is explicitly requested. The strict criterion for summary inclusion is **input q < threshold**, with a default threshold of `0.05`. The tool does **not** recompute q-values, P-values, or motif-enrichment statistics.

## Inputs

| Input | Role | Interpretation |
| --- | --- | --- |
| HOMER `knownResults.txt` (TSV) | Main input | Existing motif names and reported statistics |
| Generic TSV | Alternative main input | User-selected motif-name and optional q-value/grouping columns |
| `homer_audit/rules.tsv` (or `--rules`) | 34 provisional lexical rules | Reporting heuristics; **not** validated native TF-family assignments |
| `homer_audit/reference_name_rules_v04.tsv` | Bundled restricted reference | 10 rules; 21 explicitly permitted TF names linked to JASPAR 2026 class/family metadata |
| `--curated` | Optional user mapping | A user-supplied override; remains subject to review |
| `--reference-table` | Optional local reference comparison | Checks matches/conflicts; the program does **not** authenticate the reference |

The reference-name crosswalk is intentionally restricted to listed symbols, not all members of a TF family. The matrix IDs supplied in the crosswalk are provenance identifiers, **not** the result of software PWM matching.

## Outputs

| Output | Meaning |
| --- | --- |
| `annotated.tsv` | Input rows plus name-derived labels, native reference metadata (when allowed), semantic levels, review flags, and scientific-claim limitations |
| `summary.tsv` | Counts by **legacy provisional** `family_label` at the supplied q-value threshold; not a confirmed TF-family count |
| `summary_evidence.tsv` | Significant-record counts grouped by evidence scope, semantic category, and review action |
| `summary_restricted_name_metadata.tsv` | Significant-record counts in the restricted TF-name metadata crosswalk; not PWM-matched motifs |
| `audit.json` | Version, input/rules/reference file SHA256 hashes, counts, and interpretation warnings |
| `reference_comparison.tsv` | Additional output when `--reference-table` is provided |

`summary*` files are emitted only when `--summary` is specified. Outputs count **HOMER table records**, not independent TFs, independent experiments, validated DNA-binding events, or biological family enrichments.

For interpretation, inspect `v03_label_level`, `v03_claim_disposition`, `v03_metadata_evidence_scope`, `v03_reference_name_supported`, `v03_review_action`, `v03_reference_tf_class`, and `v03_reference_tf_family`. The legacy `family_label` is provisional. `v03_family_claim_validated` remains `FALSE`; `v03_review_required=FALSE` does **not** confer biological approval.

### Conservative handling of ambiguous labels

The classifier explicitly flags composite/dimer names, fusion/chimeric models, broad `ETS`, generic `AP-1`, multicomponent `NF-Y`, and specified member exceptions including `ATF2`, `ATF3`, `ATF6`, and `BATF`. `CTCF` is treated as a specific name, **not** evidence of TF occupancy. A user-provided reference disagreement requires review.

## Classification methodology and sources

The **implemented workflow**, complete 10-rule name crosswalk, symbol allowlists, examples, provenance, caveats, and references are documented in:

**[Methods and references — `docs/METHODS_AND_REFERENCES.md`](docs/METHODS_AND_REFERENCES.md)**

The three primary background/source publications are:

1. Heinz S, et al. (2010). *Simple combinations of lineage-determining transcription factors prime cis-regulatory elements required for macrophage and B cell identities.* **Molecular Cell**, 38:576–589. https://doi.org/10.1016/j.molcel.2010.05.004 — HOMER/motif-analysis context, **not** the source of this utility's custom lexical rule table.
2. Ovek Baydar D, et al. (2026). *JASPAR 2026: expansion of transcription factor binding profiles and integration of deep learning models.* **Nucleic Acids Research**, 54(D1):D184–D193. https://doi.org/10.1093/nar/gkaf1209 — **actual metadata source**, used as a restricted curated subset.
3. Wingender E, Schoeps T, Dönitz J. (2013). *TFClass: an expandable hierarchical classification of human transcription factors.* **Nucleic Acids Research**, 41(D1):D165–D170. https://doi.org/10.1093/nar/gks1123 — conceptual hierarchical-classification reference; the program **does not** execute or directly query TFClass.

See also [scientific scope](docs/SCIENCE_SCOPE.md), [validation and publicly pinned test sources](docs/VALIDATION.md), and [JASPAR attribution and changes](NOTICE-JASPAR.md).

## Verification

Run the included offline unit tests:

```bash
python -B -m unittest discover -s tests -q
```

Before this documentation/workflow update, RC2 passed 61 local unit tests and software regressions using three separately obtained, Git-blob-pinned public HOMER tables (1,168 records; 46 restricted name-metadata hits, 21 with input q < 0.05; 758 records flagged for review). These are **software regression observations, not sensitivity/specificity estimates or independent biological verification**. Public tables can reuse the same HOMER motif dictionary. The actual tables are **not bundled**. Reproduce those tests with user-obtained local copies as described in [VALIDATION](docs/VALIDATION.md).

## Relationship to other tools

HOMER performs motif discovery/enrichment; tools such as MEME Suite Tomtom and GimmeMotifs can compare motif matrices. **This utility does neither.** It audits downstream *reported names*, reference metadata and review dispositions. Where PWM-level identity matters, use an appropriate sequence/matrix-comparison method separately.

## License and attribution

Original code: **MIT License**, see [`LICENSE`](LICENSE). The bundled **adapted JASPAR 2026 metadata** have separate **CC BY 4.0** attribution and modification notices in [`NOTICE-JASPAR.md`](NOTICE-JASPAR.md). The MIT software license does not supersede the JASPAR data terms. No HOMER executable, HOMER motif library, JASPAR PWM collection, public external HOMER tables, or unpublished experiment-specific datasets are bundled.

This is a release-candidate research utility; users are responsible for interpreting results within the stated scientific limits.
