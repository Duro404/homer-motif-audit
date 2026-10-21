# Release review checklist — no automatic publication

- [x] Author states personally independent authorship of the original code (declaration; not independently certified)
- [x] Software MIT `LICENSE` generated with author-selected copyright holder
- [x] JASPAR 2026 CC BY 4.0 source, changes and attribution described in `NOTICE-JASPAR.md`
- [x] GitHub Actions references fixed to reviewed commit SHAs
- [x] 61 unit tests plus synthetic CLI checks passed on the isolated candidate
- [x] Three previously tested public nine-column HOMER data sources: 1,168 records; regression results verified before this documentation-only correction
- [ ] Review exact license text and source/third-party acknowledgements as the rights holder
- [ ] Run fresh staging static audit and inspect each item marked REVIEW
- [ ] Create a **new empty local Git repository**, inspect all staged files and confirm there is no inherited history or remote
- [ ] Explicitly authorize the final public push/release (not performed by any preparation script)

Name-based JASPAR metadata concordance is not PWM identity, actual TF binding,
or independent biological family validation. Tests do not establish those claims.
