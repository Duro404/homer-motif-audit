# Methods, classification decisions, evidence levels, and references

**Applies to:** HOMER Motif Audit v0.3.0-rc2. This document describes what the **shipped code** implements. Published methods, database metadata, and author-defined software heuristics are distinguished explicitly; citations do not themselves validate individual predictions.

## 1. Scope and input data

The utility reads an **existing** HOMER known-motif enrichment output (`knownResults.txt`) or a generic tab-delimited table. The motif name (e.g. `FOXA1(Forkhead)/...`) is the principal annotation input. The q-value is taken from the input and, when requested, used only to select rows for **reporting summaries**. The utility does **not** rerun HOMER, recalculate enrichment statistics, infer biological replicates, or use raw sequences or motif matrices. The HOMER methodology is described by Heinz et al. [1]; this tool's downstream textual classification rules are **author-defined**, not a published HOMER classification algorithm.

## 2. Implemented name-annotation procedure

1. **Parse name text.** Extract a motif core, its TF/model-name head, and a parenthetical descriptor (if present), with special handling of the legitimate `C/EBP` name prefix before separating HOMER provenance text at `/`. Parsing is case-insensitive for rule matching.
2. **Apply provisional rules.** By default, `homer_audit/rules.tsv` supplies **34** defined regular-expression rules against the motif head or parenthetical descriptor. Head-specific matches take precedence over descriptor-based matches. If multiple matching rules give conflicting provisional labels, the result is marked ambiguous and held for review. Any user-provided curated mapping is an override, not independently certified biological truth. The output `family_label` remains a **legacy provisional display label**, even if a rule name resembles a recognized TF family.
3. **Identify name/model ambiguity.** `homer_audit/semantic.py` detects specified fusion/chimeric models, colon-separated composites/dimers, generic family/model names, and held TF member exceptions. These checks occur before exact-symbol JASPAR mapping; an ambiguous model must not be reinterpreted as a single TF.
4. **Perform a restricted JASPAR metadata crosswalk.** For an eligible **exact TF symbol** in `homer_audit/reference_name_rules_v04.tsv`, the tool can attach JASPAR 2026 CORE **class** and **family** strings, a display alias, rule identifier, and matrix identifiers. The crosswalk has **10 selected rules and 21 eligible exact TF names**. It is not the full JASPAR catalogue. If the legacy reporting label conflicts, a supplied curated override intervenes, or a reference-table conflict/pending status is reported, scientific-claim support is withheld and review is required.
5. **Separate output claims from names.** `homer_audit/claims.py` derives origin/evidence/review fields. A successful exact-name metadata crosswalk means only *TF-name/class/family metadata support*, **not HOMER-to-JASPAR PWM equivalence**. The program does not call JASPAR online during a normal annotation run and does not compare PFM/PWM sequences, score motif similarity, or test TF occupancy. `v03_family_claim_validated`, `v03_pwm_identity_tested`, and `v03_tf_binding_proven` remain `FALSE`.
6. **Summarize existing records, if requested.** With `--summary`, rows are included when the supplied numeric input q-value is **strictly less** than `--q-threshold` (default `0.05`). There is no additional multiple-testing correction. The resulting summaries count HOMER **records**, not independent TF families or biological events. `summary.tsv` is legacy/provisional; `summary_evidence.tsv` stratifies evidence and review categories; `summary_restricted_name_metadata.tsv` includes only supported restricted name-metadata rows.
7. **Audit provenance.** `audit.json` records version, relevant SHA256 checksums, counts, and warning fields. Optional user reference tables are compared by case-insensitive exact motif core, with conflicts retained rather than silently reconciled. The software verifies input/reference **formats**, not their scientific accuracy.

## 3. Restricted JASPAR 2026 exact-name crosswalk

The following table is transcribed from the distributed `homer_audit/reference_name_rules_v04.tsv`. **These are exact allowlists**; similar TF symbols or other members of a family must not be assumed covered. The `JASPAR class` and `JASPAR family` columns preserve the reference metadata terminology; `Display` is an author-defined reporting alias, **not necessarily a native JASPAR family name**.

| Rule | Eligible exact TF symbol(s) | Display | JASPAR class | JASPAR family |
| --- | --- | --- | --- | --- |
| R03 | CEBPA, CEBPB, CEBPD | CEBP | Basic leucine zipper factors (bZIP) | CEBP-related |
| R08 | FOXA1, FOXO1 | FOX | Fork head/winged helix factors | FOX |
| R09 | SOX9 | SOX | High-mobility group (HMG) domain factors | SOX-related factors |
| R10 | MEF2A, MEF2C, MEF2D | MEF2 | MADS box factors | Regulators of differentiation |
| R11 | SRF | SRF | MADS box factors | Responders to external signals (SRF/RLM1) |
| R12 | GATA4 | GATA | Other C4 zinc finger-type factors | C4-GATA-related |
| R13 | RUNX1 | RUNX | Runt domain factors | Runt-related factors |
| R14 | SMAD3 | SMAD | SMAD/NF-1 DNA-binding domain factors | SMAD factors |
| R16 | TEAD1, TEAD4 | TEAD | TEA domain factors | TEF-1-related factors |
| R17 | ELK1, SPI1, ETS1, ERG, FLI1, ETS2 | ETS | Tryptophan cluster factors | Ets-related |

**Origin of this crosswalk:** selected and manually reviewed JASPAR 2026 CORE names/class/family metadata acquired through the public JASPAR REST API for a targeted subset of TF names (October 2026) [2]. The rule identifiers, restricted eligible-symbol sets, display aliases, and scientific-review dispositions are **added by the tool's author** and are not an official JASPAR mapping release. Matrix IDs remain in the TSV to make source lookup possible; **they were not compared with HOMER PWMs**. Cite the JASPAR 2026 publication and retain the [CC BY 4.0 attribution and modification notice](../NOTICE-JASPAR.md).

The broader TFClass framework explains the hierarchical interpretation of TF DNA-binding-domain classes and families [3]. **TFClass was used for classification background, not directly queried by this version of the program.** The JASPAR mapping is not independent corroboration from TFClass.

## 4. Ambiguous or withheld annotations

| Example name/model pattern | Conservative handling | Reason |
| --- | --- | --- |
| `FOXA1(...)`, `MEF2A(...)`, etc. (allowed exact symbols only) | May receive name-only class/family metadata, if conflict-free | Does not prove motif matrix identity or binding |
| Generic `ETS` | Broad family label; manual review | Not an identifiable specific ETS family member |
| `AP-1` / `AP1` | Multi-partner model; manual review | AP-1 may refer to different TF combinations |
| `NFY` / `NF-Y` | Multi-subunit complex; manual review | Complex name does not identify component/occupancy |
| `ATF2`, `ATF3`, `ATF6`, `BATF` | Member-exception HOLD | These are intentionally not admitted into the restricted crosswalk |
| `A:B` composite, or explicit fusion/chimeric name | Complex/fusion HOLD | Do not assign binding to a unique TF from label text alone |
| `CTCF` | Specific symbol, name-only | No evidence of direct TF binding supplied by the tool |
| Conflicting user reference or legacy rule | HOLD for review | User reference claims and metadata labels are not automatically authenticated |

`v03_review_required=FALSE` means **no additional code-defined review trigger**; it does **not** mean a binding or family claim was experimentally verified. Even a JASPAR-matched name has `v03_family_claim_validated=FALSE`.

## 5. Reproducibility and validation limitations

- RC2 passed **61** local unit tests and a three-dataset software regression on publicly available full-column HOMER result tables (**1,168** motif records; **46** restricted name-metadata hits; **21** of the 46 at reported input `q < 0.05`; **758** records flagged for review). Further validation was performed on an independent GitHub Actions environment running Python 3.10 and 3.12. These numbers describe observed program behavior, **not** a family-classification accuracy rate.
- The three external HOMER outputs may contain the same known-motif library vocabulary; they should **not** be counted as three independent biological ground-truth evaluations.
- Real external test tables are not redistributed. Fixed source commits and Git blob SHA1 identifiers, and instructions for reproducing the offline integration test, are in [`VALIDATION.md`](VALIDATION.md).
- No held-out experimental PWM matching, TFChIP binding validation, sensitivity/specificity or direct family assignment benchmark was performed. The 10 rules do not license applying the mappings to unlisted TFs.
- For publication-grade biological claims, supplement any textual labels with domain-specific review and/or validated PWM comparison and biological evidence as appropriate.

## 6. References and role in this software

**[1] HOMER origin / upstream motif-analysis framework — background, not the source of the software's custom name rules.**  
Heinz S, Benner C, Spann N, Bertolino E, Lin YC, Laslo P, Cheng JX, Murre C, Singh H, Glass CK. (2010). **Simple combinations of lineage-determining transcription factors prime cis-regulatory elements required for macrophage and B cell identities.** *Molecular Cell*. 38(4):576–589. https://doi.org/10.1016/j.molcel.2010.05.004

**[2] JASPAR 2026 — actual upstream metadata source for the restricted name/class/family crosswalk.**  
Ovek Baydar D, Rauluseviciute I, Aronsen DR, et al. (2026). **JASPAR 2026: expansion of transcription factor binding profiles and integration of deep learning models.** *Nucleic Acids Research*. 54(D1):D184–D193. https://doi.org/10.1093/nar/gkaf1209  
Database: https://jaspar.elixir.no/ ; API: https://jaspar.elixir.no/api/ ; license: https://creativecommons.org/licenses/by/4.0/ . See [`NOTICE-JASPAR.md`](../NOTICE-JASPAR.md) for modified data attribution and non-endorsement.

**[3] TFClass — conceptual background for hierarchical TF classification; not directly queried or merged into reference rows.**  
Wingender E, Schoeps T, Dönitz J. (2013). **TFClass: an expandable hierarchical classification of human transcription factors.** *Nucleic Acids Research*. 41(Database issue):D165–D170. https://doi.org/10.1093/nar/gks1123

**Method provenance disclaimer:** Citations [1]–[3] support HOMER context, the JASPAR reference resource, and hierarchical TF taxonomy. The **34 regex rules**, the **10 bounded crosswalk selections**, conflict gates, and review categories are this utility's software implementation and its author's curation decisions. They were **not** established as an externally validated new biological taxonomy by these publications.
