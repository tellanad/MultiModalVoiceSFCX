"""Vercel api/main.py entrypoint."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from axiomcart.main import app  # noqa: E402, F401
