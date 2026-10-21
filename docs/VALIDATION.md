# Verification record and reproducibility limits

## RC2 original server regression (before preparing this release preview)

- Three publicly hosted HOMER full-column `knownResults.txt` tables, pinned at Git commits; 1,168 motif rows in total.
- 46 restricted TF-name-metadata hits, 21 of those with input q < 0.05.
- 758 records requiring a conservative review action.
- 0 scientifically validated motif family/PWM/TF-occupancy claims.
- RC2 local unit tests: 61/61. The release preview modifies only distribution layout, one location restriction in its **optional** public integration wrapper, and tests previously coupled to internal historical code.

These are SOFTWARE BEHAVIOR REGRESSION results. Public HOMER outputs may reuse an identical underlying known-motif vocabulary. No accuracy or sensitivity/specificity claim can be derived from these figures.

## Pinned public sources (not distributed in this repository)

| File expected under `--source-dir` | GitHub project | Commit / blob SHA1 |
| --- | --- | --- |
| `qbio_2018_knownResults.txt` | [qbio-gsk/qbio-gsk](https://github.com/qbio-gsk/qbio-gsk/blob/1568600064e39a2d89a05397563c8c91b7a7ec86/2018/lab8/motifs/homer-output/knownResults.txt) | blob `2d47508cebdfb496d2a62f560c8f2785493acf1b` |
| `plate_scATAC_cluster1_knownResults.txt` | [dbrg77/plate_scATAC-seq](https://github.com/dbrg77/plate_scATAC-seq/blob/81a158b5386755b02e38042abadf2840b1add4a8/mSp_scATAC-seq/homer_motifs/cluster_1_homer_knownResults.txt) | blob `c421ce4a78273910db478ee7fab126c1c8286b69` |
| `fetal_brain_ctcf_topic9_knownResults.txt` | [linnarsson-lab/fetal_brain_multiomics](https://github.com/linnarsson-lab/fetal_brain_multiomics/blob/ceaeb992d767f44589a4999fc7e34a492d5d30de/files/Figure_2/homer_CTCF/Topic_9/knownResults.txt) | blob `07ba17ad46a4b27dac27958186c154f93af9469c` |

Use separately downloaded public files only after checking usage rights; the repository does not redistribute them. The integration script checks the pinned Git blob SHA1 before any output is written, and refuses an existing output directory. It uses the unchanged RC2 scientific claims logic.

## Interpretation boundaries

- Name crosswalk is not PWM identity.
- q<0.05 relates to original HOMER output rows, not an independent TF family truth set.
- No linked user-specific or unpublished datasets are included.
- RC2 release preview must pass fresh isolated unit tests and synthetic smoke tests before publishing. See `docs/RELEASE_CHECKLIST.md`.
