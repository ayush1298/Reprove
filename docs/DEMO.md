# Two-minute demo script

1. Open `dashboard/index.html`. Lead with: **“No fix without a failing test.”**
2. Run the issue command below. Point out five red evidence runs, then five green runs, the mutation kill, and the branch-ready artifacts.
3. Show `examples/seeded-repo/.reprove/issue-42/issue-comment.md` and `pull-request.md`.
4. Show the refusal unit test (`tests/test_safety.py`): changing a test or weakening its assertions is rejected before apply.
5. Run the upgrade command. Its old-behavior canary turns red after the bump even though this represents a semantic default change, not a compile error.
6. Close on `reports/public-issue-replay-pilot.json`: the demo has a measured public upstream replay (3/3 fail on the pinned baseline, pass on the accepted fix; N=1), alongside a clearly unscored SWE-bench follow-on protocol.

```bash
python -m reprove.cli verify-fix --repo examples/seeded-repo \
  --claim "Exports at exactly 100 records are rejected" \
  --test tests/test_export_limit.py \
  --command "python -m pytest tests/test_export_limit.py" \
  --nearby "python -m pytest tests" \
  --change examples/seeded-repo/fix.json --issue 42

python -m reprove.cli upgrade --repo examples/upgrade-demo \
  --upgrade examples/upgrade-demo/upgrade.json \
  --nearby "python -m pytest tests"
```
