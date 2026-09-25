# How `reports/report.pdf` is produced

Every number in the report is measured, by these three scripts, from the code
as it stands. Run from the repository root:

```bash
export QT_QPA_PLATFORM=offscreen SIF_ENCODER=hashing
python reports/tools/collect_tests.py   reports/tools/tests.json     # every test, one by one
python reports/tools/collect_metrics.py reports/tools/metrics.json   # accuracy, model, speed, size
python reports/tools/build_report.py    reports/report.pdf
```

`tests.json` and `metrics.json` here are the measurements the committed
`report.pdf` was built from. Screens come from `docs/`.
