import re, numpy as np, pandas as pd

def load_monthly(path, ncols_expected=None):
    """Parse a Ken French monthly CSV: rows starting with a 6-digit YYYYMM, stop at the first 'Annual' header
    after data started. Returns DataFrame indexed by pandas Period('M')."""
    rows = []
    cols = None
    started = False
    with open(path) as f:
        lines = f.read().splitlines()
    for ln in lines:
        m = re.match(r'^\s*(\d{6})\s*,(.*)$', ln)
        if m:
            started = True
            vals = [x.strip() for x in m.group(2).split(',')]
            rows.append([m.group(1)] + vals)
        else:
            if started and ln.strip() == '':
                # blank after data block -> end of monthly block
                break
            if started and 'Annual' in ln:
                break
    return rows

def load_daily(path):
    rows = []
    started = False
    with open(path) as f:
        for ln in f:
            m = re.match(r'^\s*(\d{8})\s*,(.*)$', ln)
            if m:
                started = True
                rows.append([m.group(1)] + [x.strip() for x in m.group(2).split(',')])
            elif started and ln.strip() == '':
                break
    return rows
