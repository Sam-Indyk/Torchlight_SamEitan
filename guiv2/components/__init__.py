"""Renderer registry for guiv2.

Adding a new view type:
  1. Create a new module here that exposes a render_<name>(view, manifest)
     function.
  2. Import and register it in the RENDERERS dict below.
  3. Reference it in guiv2/manifest.json with `"type": "<name>"`.
"""

from .honesty_banner    import render_honesty_banner
from .per_subject_table import render_per_subject_table
from .pooled_table      import render_pooled_table
from .risk_overview     import render_risk_overview
from .risk_axis_panel   import render_risk_axis_panel
from .flow_diagram      import render_flow_diagram
from .report_card       import render_report_card
from .multi_system_panel import render_multi_system_panel

RENDERERS = {
    "per_subject_table": render_per_subject_table,
    "pooled_table":      render_pooled_table,
    "risk_overview":     render_risk_overview,
    "risk_axis_panel":   render_risk_axis_panel,
    "flow_diagram":      render_flow_diagram,
    "astronaut_report_card": render_report_card,
    "multi_system_panel":   render_multi_system_panel,
}
