"""Quick inspection of dashboard_data.json - prints axis trajectories."""
import json
import sys
from pathlib import Path

p = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parent.parent / "data" / "dashboard_data.json")
d = json.loads(p.read_text(encoding="utf-8"))

print(f"=== {p}")
print(f"timepoints: {d['metadata']['timepoints']}")
print()
for ax in d["axes"]:
    flags = []
    if ax.get("is_mock"):         flags.append("MOCK")
    if ax.get("is_cohort_level"): flags.append("COHORT")
    print(f"--- {ax['id']:14s} {ax['label']}  {' '.join(flags)}")
    for crew in ("C001", "C002", "C003", "C004"):
        scores = ax["trajectories"][crew]["scores"]
        pretty = ["  -- " if s is None else f"{s:+5.2f}" for s in scores]
        print(f"  {crew}: " + " ".join(pretty))
    print(f"  within-cohort: {ax['within_cohort_comparison']['summary']}")
    print()
