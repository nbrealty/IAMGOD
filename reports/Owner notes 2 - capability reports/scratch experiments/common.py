"""Scratch helpers for the capability experiments (NOT part of the repo). Imports the repo's own test harness."""
import sys, os
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/user/IAMGOD/trading")
sys.path.insert(0, "/home/user/IAMGOD/trading/tests")
import importlib
T = importlib.import_module("test_scalp_live_engine")   # H, mkbars, ts, REG, ... (module-level code only loads the registry)
from lab.scalp.live import config as C
from lab.scalp.live.model import *  # noqa
import pandas as pd
