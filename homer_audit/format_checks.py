"""HOMER knownResults.txt TSV header recognition. No inference from filenames."""
from __future__ import annotations

import re
from typing import List


def canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def detected_format(columns: List[str], requested: str) -> str:
    if requested not in {"auto", "homer-known", "generic-tsv"}:
        raise ValueError("Invalid --input-format")
    keys = [canon(c) for c in columns]
    is_known = ("motifname" in keys and "consensus" in keys
                and any(k.startswith("qvalue") for k in keys))
    if requested == "homer-known":
        # Full set of 9 columns is *not* required because different HOMER
        # releases and post-processing can alter auxiliary columns.
        if not is_known:
            raise ValueError("--input-format homer-known requires Motif Name, Consensus, and q-value headers")
        return "homer-known"
    if requested == "generic-tsv":
        return "generic-tsv"
    return "homer-known" if is_known else "generic-tsv"
