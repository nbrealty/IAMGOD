"""V4-14 scratch S3: a REPLACEMENT worker starts while the OLD worker is still alive (partitioned, not dead).
A holds a protected 1-share position. B starts, rebuilds from the broker (restore.rebuild) and ADOPTS the same position.
Both then run to the 15:50 flatten and beyond. Shared SimBroker = the one account."""
import tempfile, pathlib
from common import *
from e4_v414 import snap, tick_both     # noqa (re-runs S1/S2 prints once on import; ignore)
