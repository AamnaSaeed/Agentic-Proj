"""Adds the project root to sys.path so imports resolve correctly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
