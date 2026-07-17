# Silent-upgrade canary demo

```bash
reprove upgrade --repo examples/upgrade-demo --upgrade examples/upgrade-demo/upgrade.json \
  --nearby "python -m pytest tests"
```

The canary first pins the application's v1 behavior (green five times). The v2
bump leaves the project structurally valid, but flips that behavior red; Reprove
reports an execution-backed silent compatibility break instead of a vague warning.
