from .per_subject_table import render_per_subject_table
from .pooled_table import render_pooled_table
from .flow_diagram import render_flow_diagram
from .honesty_banner import render_honesty_banner

RENDERERS = {
    "per_subject_table": render_per_subject_table,
    "pooled_table": render_pooled_table,
    "flow_diagram": render_flow_diagram,
}
