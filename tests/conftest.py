"""Adds the project root to sys.path so imports resolve correctly."""
import sys
from pathlib import Path

IMAGEMAGICK_BINARY = r"D:\ImageMagick-7.1.2-Q16\magick.exe"

sys.path.insert(0, str(Path(__file__).parent.parent))
