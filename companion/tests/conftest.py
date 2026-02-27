"""
Pytest configuration and fixtures for companion tests
"""

import sys
from pathlib import Path

# Add companion module to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
