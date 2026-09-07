# Manual check scripts

These are **not** tests. They are one-off scripts that print output for a human
to read; they contain no assertions and nothing fails them.

They were previously named `test_*.py` in `agent/`, where pytest would collect
them and where they gave the misleading impression that the project had a test
suite. The real suite lives in `agent/tests/`.

Run them directly when debugging:

```bash
python scripts/manual/check_imports.py
```
