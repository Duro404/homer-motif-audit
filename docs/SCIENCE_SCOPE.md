# Scientific method and interpretation boundaries

1. **Lexical annotation**: parse HOMER motif labels; match explicit names/regular expressions. This is a textual annotation of the reported motif name, not a direct inference from DNA-binding sequence.
2. **Restricted JASPAR reference**: only 10 limited TF-name rules and listed symbols; the class/family strings are retained as native metadata. Different TFs may have multiple JASPAR matrices. The software has not compared actual matrices.
3. **Claim separation**: provisional name-rule label (`family_label`), native reference family (`v03_reference_tf_family`), and reporting group (`v03_display_group`) are not equivalent concepts.
4. **Review vs approval**: `v03_review_required` indicates flagged handling. `FALSE` is not an assertion of scientific validation. Withheld or ambiguous names should not automatically enter a confirmed family analysis.
5. **Composite/fusion models**: partners, dimers and fusions should not be silently interpreted as binding by any single TF.
6. **Statistical evidence**: the tool reports counts of HOMER output records using supplied q-values; it does not calculate enrichment statistics, perform genome-level inference or establish independent replicates.
7. **No biological accuracy estimate**: publicly shared motif output tables can reuse the same underlying HOMER motif dictionary. Concordance counts are software regressions, not independent biological truth.

Selected background reading (not endorsements of this tool):
- TFClass hierarchical classifications: https://doi.org/10.1093/nar/gks1123
- JASPAR 2026: https://doi.org/10.1093/nar/gkaf1209
- HOCOMOCO 2024: https://doi.org/10.1093/nar/gkad1077
- RSAT matrix clustering: https://doi.org/10.1093/nar/gkx314

This source bundle contains no JASPAR PWM files, no independently verified TFClass record-level crosswalk, and no proof of binding.
