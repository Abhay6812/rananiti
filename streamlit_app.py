"""Root-level Streamlit deployment entry point."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "dashboard" / "app.py"), run_name="__main__")
