"""Run every suite, record each test's outcome and duration."""
import json, os, sys, time, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIF_ENCODER", "hashing")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)

class Recorder(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.records = []; self._t = {}
    def startTest(self, test):
        self._t[test.id()] = time.perf_counter(); super().startTest(test)
    def _rec(self, test, status, detail=""):
        self.records.append({"id": test.id(), "status": status, "detail": detail[:300],
                             "seconds": round(time.perf_counter() - self._t.get(test.id(), time.perf_counter()), 3),
                             "doc": (test.shortDescription() or "")})
    def addSuccess(self, t): super().addSuccess(t); self._rec(t, "pass")
    def addFailure(self, t, e): super().addFailure(t, e); self._rec(t, "fail", self._exc_info_to_string(e, t))
    def addError(self, t, e): super().addError(t, e); self._rec(t, "error", self._exc_info_to_string(e, t))
    def addSkip(self, t, r): super().addSkip(t, r); self._rec(t, "skip", r)

suite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")
with open(os.devnull, "w") as sink:
    runner = unittest.TextTestRunner(stream=sink, resultclass=Recorder, verbosity=0)
    started = time.perf_counter(); result = runner.run(suite); total = time.perf_counter() - started
out = {"total_seconds": round(total, 1), "records": result.records}
json.dump(out, open(sys.argv[1], "w"), indent=1)
from collections import Counter
print(Counter(r["status"] for r in result.records), "in", round(total,1), "s")
