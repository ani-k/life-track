import pytest

# Make the app package importable from tests/
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
