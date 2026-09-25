"""Engine accuracy on the second labelled set, model CV metrics, speed, code size."""
import csv, json, os, sys, tempfile, time
os.environ.setdefault("SIF_ENCODER", "hashing")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from sif import SIFPipeline
from sif.encoders import HashingEncoder

out = {}
pipe = SIFPipeline(encoder=HashingEncoder())

def score(path, text_key, label_key, rule_key):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    tp = fp = fn = tn = rule_ok = rule_n = queued = 0
    for r in rows:
        res = pipe.analyze(r[text_key]); y = int(r[label_key]); p = int(bool(res.sif_potential))
        tp += y and p; fp += (not y) and p; fn += y and not p; tn += (not y) and not p
        if y and p and r.get(rule_key):
            rule_n += 1; rule_ok += res.iogp_rule == r[rule_key]
        queued += bool(res.needs_review)
    prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0
    return {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 3),
            "recall": round(rec, 3), "f1": round(2*prec*rec/(prec+rec), 3) if prec+rec else 0,
            "rule_accuracy": round(rule_ok / rule_n, 3) if rule_n else None, "queued": queued}

out["eval42"] = score("evaluation/labelled_reports.csv", "report", "sif", "rule")
out["train56"] = score("samples/training_corpus.csv", "report", "sif_label", "rule")

# speed: the 18-report sample, engine only
from main import read_csv_reports
narr, refs = read_csv_reports("samples/near_miss_reports.csv")
pipe.analyze(narr[0])
t = time.perf_counter()
for n in narr: pipe.analyze(n)
out["ms_per_report"] = round((time.perf_counter() - t) / len(narr) * 1000, 2)
out["reports_per_minute"] = int(60000 / out["ms_per_report"])

# the learned model: train on the 56-report corpus, cross-validated
from sif.mlops import MLOpsService, FEATURE_NAMES
tmp = tempfile.mkdtemp()
svc = MLOpsService(model_directory=os.path.join(tmp, "m"), tracking_uri=f"sqlite:///{tmp}/ml.db")
rows = list(csv.DictReader(open("samples/training_corpus.csv", encoding="utf-8")))
results = [pipe.analyze(r["report"]) for r in rows]
labels = [int(r["sif_label"]) for r in rows]
try:
    rep = svc.train(results, labels=labels, label_source="training_corpus.csv")
    out["model"] = {k: getattr(rep, k, None) for k in ("samples", "positives", "cv_folds")}
    out["model"]["metrics"] = {k: (round(v, 3) if isinstance(v, float) else v)
                               for k, v in (rep.metrics or {}).items()}
    out["model"]["top_features"] = [(n, round(float(v), 3)) for n, v in (rep.importances or [])[:8]]
    out["model"]["warnings"] = list(getattr(rep, "warnings", []) or [])
except Exception as exc:
    out["model"] = {"error": str(exc)}
out["features"] = len(FEATURE_NAMES)

# code size
loc = {}
for top in ("sif", "ui", "ui2"):
    for f in sorted(os.listdir(top)):
        if f.endswith(".py"):
            loc[f"{top}/{f}"] = sum(1 for _ in open(os.path.join(top, f), encoding="utf-8"))
for f in ("main2.py", "main.py", "app.py", "app2.py", "train_model.py"):
    loc[f] = sum(1 for _ in open(f, encoding="utf-8"))
tests = {f: sum(1 for _ in open(f, encoding="utf-8")) for f in sorted(os.listdir(".")) if f.startswith("test_") and f.endswith(".py")}
out["loc"] = loc; out["test_loc"] = tests
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k not in ("loc", "test_loc")}, indent=1, default=str))
