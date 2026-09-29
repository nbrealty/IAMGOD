import numpy as np
import importlib.util, sys
spec = importlib.util.spec_from_file_location("x14_adx_mod", "x14_adx.py")
# re-implement quickly without executing the main body of x14_adx.py
src = open("x14_adx.py").read().split("# 1) Cross-check")[0]
ns = {}
exec(src, ns)
my_adx, make_bars = ns["my_adx"], ns["make_bars"]
import numpy as np
for m in (5, 20):
    H, L, C = make_bars(300, 1500, m)
    sh = [np.mean(my_adx(H[k], L[k], C[k])[100:] > 25) for k in range(300)]
    print(f"my own Wilder ADX (no TA-Lib), m={m}: share ADX>25 = {np.mean(sh):.3f}")
