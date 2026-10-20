"""Vercel serverless function entrypoint."""
import os
import sys

# Ensure src/ is on the Python path in the Vercel serverless runtime
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from axiomcart.main import app

# Vercel looks for the ASGI app callable
