# Review Benchmarks

Reference hardware for v0.2 acceptance:

- CPU: Apple M-series (any), 8 cores
- RAM: 16GB
- Python: 3.11.x
- torch: latest CPU build (no CUDA)

Acceptance budgets refer to this baseline. Variations on different hardware are expected;
report when running on non-reference hardware via `--benchmark-report`.

## Candidate-pair density

L2 budget "≤ 30s on 1000 candidate pairs" assumes:
- Rule corpus 200-500 chunks
- L1 produces ≤ 5 candidate pairs per chunk (cap)
- Final L2 input ≤ 1000 pairs after dedup
