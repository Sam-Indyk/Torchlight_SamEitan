"""Peek at OSD-575 cytokine analyte names and value scale."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from build_risk_profile import (
    ANALYSIS_CACHE, CACHE_FILES, load_serum_csv, parse_sample,
    extract_reference_ranges, INFLAMMATION_NEEDLES, IMMUNE_NEEDLES,
)

for key in ("OSD-575_immune_eve", "OSD-575_immune_alamar"):
    path = ANALYSIS_CACHE / CACHE_FILES[key]
    df = load_serum_csv(path)
    if df is None:
        print(f"{key}: missing"); continue
    print(f"=== {key}  shape={df.shape}")
    needles = [s.lower() for s in (INFLAMMATION_NEEDLES + IMMUNE_NEEDLES)]
    for label in df.index[:50]:
        s = str(label).lower()
        if "_percent" in s or "range_min" in s or "range_max" in s:
            continue
        if any(n in s for n in needles):
            row = pd.to_numeric(df.loc[label], errors="coerce").dropna()
            if len(row) == 0: continue
            print(f"  {str(label)[:80]:80s}  median={row.median():.3g}  "
                  f"min={row.min():.3g}  max={row.max():.3g}  n={len(row)}")
    print()

# also dump matching analyte labels
def _safe(s): return str(s).encode("ascii", "replace").decode("ascii")

key_targets = ["il_6", "il6", "il_10", "il10", "il_4", "il4", "il_2", "il2",
               "tnf", "crp", "ifn", "interferon", "tgf"]
for key in ("OSD-575_immune_eve", "OSD-575_immune_alamar",
            "OSD-575_cardio_eve"):
    print(f"=== {key} - relevant analytes:")
    df = load_serum_csv(ANALYSIS_CACHE / CACHE_FILES[key])
    if df is None:
        continue
    for label in df.index:
        s = str(label).lower()
        if "_percent" in s or "range" in s: continue
        if any(t in s for t in key_targets):
            row = pd.to_numeric(df.loc[label], errors="coerce").dropna()
            if not len(row): continue
            print(f"  {_safe(label)[:75]:75s}  median={row.median():.3g}  n={len(row)}")
    print()
