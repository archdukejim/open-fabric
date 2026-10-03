# tests/docs

The `docs` suite: the documentation says what the code does. No Docker, no
root: `python3 tests/docs/run.py`.

| File | What |
|---|---|
| `run.py` | The suite: runs the four checks below |
| `check_docstrings.py` | Every product function has a structured docstring (Purpose, Inputs, Returns, Fails, Feeds) |
| `gen_lib_doc.py` | Generate `docs/lib-doc/` from those docstrings (`--check`: is it current?) |
| `check_consistency.py` | Docs and code agree: READMEs, settings, commands, agent routes, permissions, suites, setup steps, links |
| `review_ledger.py` | The review ledger: every file reviewed, and which changed since (`--mark` after reviewing) |
| `docstring_only_diff.py` | Prove a documentation pass changed no code (syntax trees without docstrings compared) |
| `product_code.py` | The product files and functions the checks inspect, and the docstring parser |
| `call_graph.py` | Static callers of every Python function ("Called by" in `docs/lib-doc/`) |

The structured docstring (shell functions: the same labels in the comment
block above the function):

```
Purpose: what it is for
Inputs:  each argument: type, constraints ("none" if it takes none)
Returns: the result on success
Fails:   each way it fails and what the caller sees ("never" + why)
Feeds:   which functions use the result ("—" if none)
```
