# tests/docs

The `docs` suite: the documentation says what the code does. No Docker, no
root: `python3 tests/docs/run.py`.

| File | What |
|---|---|
| `run.py` | The suite: runs the four checks below |
| `check_docstrings.py` | Every product function has a structured docstring (Purpose, Inputs, Returns, Fails, Feeds) |
| `gen_lib_doc.py` | Generate the function reference (manual 1.11) from those docstrings, with the Volume 1 index (`--check`: is it current?) |
| `lib_doc_registry.py` | The reference's numbers: given once, never reused (manual 1.11.1.2) |
| `lib_doc_numbers.tsv` | Every number the reference has ever given (written by `gen_lib_doc.py`) |
| `check_consistency.py` | Docs and code agree: READMEs, settings, commands, agent routes, permissions, suites, setup steps, links |
| `review_ledger.py` | The review ledger: every file reviewed, and which changed since (`--mark` after reviewing) |
| `docstring_only_diff.py` | Prove a documentation pass changed no code (syntax trees without docstrings compared) |
| `product_code.py` | The product files and functions the checks inspect, and the docstring parser |
| `call_graph.py` | Static callers of every Python function ("Called by" in the function reference, manual 1.11) |

The structured docstring (shell functions: the same labels in the comment
block above the function):

```
Purpose: what it is for
Inputs:  each argument: type, constraints ("none" if it takes none)
Returns: the result on success
Fails:   each way it fails and what the caller sees ("never" + why)
Feeds:   which functions use the result ("—" if none)
```
