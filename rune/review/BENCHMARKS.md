# Review Benchmarks

Reference hardware for v0.2 acceptance:

- CPU: Apple M-series (any), 8 cores
- RAM: 16GB
- Python: 3.11.x
- torch: latest CPU build (no CUDA)

Acceptance budgets refer to this baseline. Variations on different hardware are expected;
report when running on non-reference hardware via `--benchmark-report`.

## L1 corpus-level baseline (informational)

`tests/test_l1_corpus_eval.py::test_l1_corpus_pr_baseline` measures pair-level P/R
when ALL 40 fixture files are loaded as one corpus. This is a *realistic* metric vs.
the synthetic per-file P/R in `test_l1_precision_recall.py`.

Baseline as of 2026-06-12 commit `<commit-of-this-PR>`:
- TP: 20
- FP: 4
- FN: 0
- Precision: 0.83
- Recall: 1.00

Threshold floor (test gates at): P ≥ 0.50, R ≥ 0.30.

## Candidate-pair density

L2 budget "≤ 30s on 1000 candidate pairs" assumes:
- Rule corpus 200-500 chunks
- L1 produces ≤ 5 candidate pairs per chunk (cap)
- Final L2 input ≤ 1000 pairs after dedup
