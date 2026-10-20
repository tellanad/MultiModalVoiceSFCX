"""Root FastAPI entrypoint for Vercel and production deployments."""
import os
import sys

# Add src directory to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from axiomcart.main import app  # noqa: E402, F401
