"""Regenerate current report figures without compiling LaTeX.
Legacy hand-entered algorithm rankings and latency charts are not regenerated.
"""
from pathlib import Path
import runpy
root = Path(__file__).resolve().parent
for script in ["make_report_diagrams.py", "generate_synthetic_evaluation.py", "generate_interval_evaluation.py", "evaluate_interval_arithmetic.py"]:
    runpy.run_path(str(root / script), run_name="__main__")
