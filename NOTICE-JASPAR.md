# JASPAR 2026 data attribution and modification notice

The software code and the JASPAR-derived metadata are different licensing layers.

**Underlying resource:** JASPAR 2026, https://jaspar2026.elixir.no/ ; JASPAR REST API: https://jaspar2026.elixir.no/api/ . The JASPAR project states that its database is licensed under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

**Publication to cite:** Baydar Ovek D et al. (2026). *JASPAR 2026: expansion of transcription factor binding profiles and integration of deep learning models*. Nucleic Acids Research, 54(D1), D184–D193. https://doi.org/10.1093/nar/gkaf1209

**Adapted material:** `homer_audit/reference_name_rules_v04.tsv` contains a small, manually selected and adapted TF-name/class/family crosswalk based on a targeted subset of JASPAR 2026 CORE metadata obtained via its public REST API (October 2026). It is NOT the complete JASPAR CORE dataset. It retains selected original TF classification strings, adds a limited TF allowlist, simplified display aliases and metadata-level interpretation restrictions. Matrix IDs are retained for provenance, but no JASPAR PFM/PWM models are bundled.

**Changes and non-endorsement:** These selections, aliases, review dispositions and rule scope were added by the independent tool author; they are not an official JASPAR classification release or an endorsement by the JASPAR maintainers. TF-name correspondence does not prove PWM identity or direct TF binding.

**Licensing scope:** Any software MIT license applies to the original software code. The JASPAR-sourced content remains subject to the attribution and other applicable requirements of CC BY 4.0. Redistributors should retain this notice, source links and modification notice. No HOMER executable, HOMER motif library, or downloaded third-party `knownResults.txt` files are redistributed in this package.
