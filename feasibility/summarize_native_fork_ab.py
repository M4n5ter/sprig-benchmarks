#!/usr/bin/env python3
"""Use the same strict summary with the separately fixed fork source pins."""
from pathlib import Path
import runpy
import native_fork_ab  # installs the exact source pins before summary imports
runpy.run_path(str(Path(__file__).with_name('summarize_lifecycle_ab.py')), run_name='__main__')
