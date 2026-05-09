"""Print the recovery block per astronaut per axis from dashboard_data.json."""
import json, sys
from pathlib import Path

p = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parent.parent / "data" / "dashboard_data.json")
d = json.loads(p.read_text(encoding="utf-8"))

print(f"=== {p.name}\n")
print(f"{'axis':<14} {'crew':<5} {'tau':>7} {'half-life':>10} "
      f"{'A':>7} {'r2':>5} {'n':>3}  qual")
print("-" * 60)
for ax in d["axes"]:
    aid = ax["id"]
    for crew in ("C001", "C002", "C003", "C004"):
        rec = ax["trajectories"][crew].get("recovery")
        if rec is None:
            print(f"{aid:<14} {crew:<5} {'-':>7} {'-':>10} {'-':>7} {'-':>5} "
                  f"{'-':>3}  -")
            continue
        tau = rec.get("tau_days")
        hl  = rec.get("half_life_days")
        a   = rec.get("initial_deviation")
        r2  = rec.get("r_squared")
        n   = rec.get("n_points_used")
        q   = rec.get("fit_quality")
        print(f"{aid:<14} {crew:<5} "
              f"{(f'{tau:.1f}' if tau is not None else '-'):>7} "
              f"{(f'{hl:.1f}' if hl is not None else '-'):>10} "
              f"{(f'{a:+.2f}' if a is not None else '-'):>7} "
              f"{(f'{r2:.2f}' if r2 is not None else '-'):>5} "
              f"{(str(n) if n is not None else '-'):>3}  {q or '-'}")
    print()
