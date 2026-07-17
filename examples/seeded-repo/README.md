# Seeded Reprove demo

This intentionally contains an off-by-one bug. From the project root, run:

```bash
reprove verify-fix --repo examples/seeded-repo \
  --claim "Exports at exactly 100 records are rejected" \
  --test tests/test_export_limit.py \
  --command "python -m pytest tests/test_export_limit.py" \
  --nearby "python -m pytest tests" \
  --change examples/seeded-repo/fix.json --issue 42
```

The first evidence run is red five times. The source-only patch is then accepted,
the evidence turns green five times, the `>=` mutation is killed, and the local
evidence-bundle artifacts are written under `.reprove/issue-42/`.
