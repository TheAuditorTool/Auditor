# TheAuditor Smoke Test Report

**Date:** 2025-12-05 23:21:41
**Total Tests:** 114
**Passed:** 102
**Failed:** 12
**Duration:** 1727.5s

## FAILURES DETECTED

The following commands crashed or exited with non-zero codes.

**Instructions for fixing:** Each failure below includes:
- The exact command that failed
- Exit code and duration
- Error summary extracted from stderr/logs
- Full stderr output (truncated)
- Internal log content from THEAUDITOR_LOG_FILE

### Failure 1: `aud taint`

- **Phase:** invoke
- **Exit Code:** TIMEOUT
- **Duration:** 600.00s

**Error Summary:**
```
Command timed out after 600s
```

---

### Failure 2: `aud deps`

- **Phase:** invoke
- **Exit Code:** 1
- **Duration:** 0.68s

**Error Summary:**
```
Full traceback logged to: .pf\error.log
```

**Stderr (last 1500 chars):**
```python
Error: OperationalError: no such column: dependencies

Full traceback logged to: .pf\error.log

```

**Internal Logs (THEAUDITOR_LOG_FILE):**
```json
{"level": 50, "time": 1764951693110, "msg": "Command 'deps' failed: no such column: dependencies", "pid": 21308, "request_id": "2e6a9249-b715-46d3-b8c5-d9bcc8fe1cb6", "cmd": "deps", "err": {"type": "OperationalError", "message": "no such column: dependencies"}}

```

---

### Failure 3: `aud deps --offline`

- **Phase:** invoke
- **Exit Code:** 1
- **Duration:** 0.69s

**Error Summary:**
```
Full traceback logged to: .pf\error.log
```

**Stderr (last 1500 chars):**
```python
Error: OperationalError: no such column: dependencies

Full traceback logged to: .pf\error.log

```

**Internal Logs (THEAUDITOR_LOG_FILE):**
```json
{"level": 50, "time": 1764951693783, "msg": "Command 'deps' failed: no such column: dependencies", "pid": 5068, "request_id": "7deccf37-053b-42ca-93f7-2843a0cf48b3", "cmd": "deps", "err": {"type": "OperationalError", "message": "no such column: dependencies"}}

```

---

### Failure 4: `aud metadata`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.74s

**Stderr (last 1500 chars):**
```python


```

---

### Failure 5: `aud workset show`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.67s

**Error Summary:**
```
Error: Got unexpected extra argument (show)
```

**Stderr (last 1500 chars):**
```python
Usage: aud workset [OPTIONS]
Try 'aud workset --help' for help.

Error: Got unexpected extra argument (show)

```

---

### Failure 6: `aud workset list`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.63s

**Error Summary:**
```
Error: Got unexpected extra argument (list)
```

**Stderr (last 1500 chars):**
```python
Usage: aud workset [OPTIONS]
Try 'aud workset --help' for help.

Error: Got unexpected extra argument (list)

```

---

### Failure 7: `aud cfg theauditor/cli.py`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.63s

**Error Summary:**
```
Error: No such command 'theauditor/cli.py'.
```

**Stderr (last 1500 chars):**
```python
Usage: aud cfg [OPTIONS] COMMAND [ARGS]...

Error: No such command 'theauditor/cli.py'.

```

---

### Failure 8: `aud cfg analyze theauditor/cli.py`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.66s

**Error Summary:**
```
Error: Got unexpected extra argument (theauditor/cli.py)
```

**Stderr (last 1500 chars):**
```python
Usage: aud cfg analyze [OPTIONS]
Try 'aud cfg analyze --help' for help.

Error: Got unexpected extra argument (theauditor/cli.py)

```

---

### Failure 9: `aud impact theauditor/cli.py`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.72s

**Error Summary:**
```
Error: Got unexpected extra argument (theauditor/cli.py)
```

**Stderr (last 1500 chars):**
```python
Usage: aud impact [OPTIONS]
Try 'aud impact --help' for help.

Error: Got unexpected extra argument (theauditor/cli.py)

```

---

### Failure 10: `aud refactor extract theauditor/cli.py --function main`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.69s

**Error Summary:**
```
Error: No such option: --function
```

**Stderr (last 1500 chars):**
```python
Usage: aud refactor [OPTIONS]
Try 'aud refactor --help' for help.

Error: No such option: --function

```

---

### Failure 11: `aud docker-analyze`

- **Phase:** invoke
- **Exit Code:** 1
- **Duration:** 0.65s

**Error Summary:**
```
Full traceback logged to: .pf\error.log
```

**Stderr (last 1500 chars):**
```python
Error: ModuleNotFoundError: No module named 'theauditor.docker_analyzer'

Full traceback logged to: .pf\error.log

```

**Internal Logs (THEAUDITOR_LOG_FILE):**
```json
{"level": 50, "time": 1764951700020, "msg": "Command 'docker_analyze' failed: No module named 'theauditor.docker_analyzer'", "pid": 30004, "request_id": "bb5696fe-f8e7-44d9-8093-aba81dff5e45", "cmd": "docker_analyze", "err": {"type": "ModuleNotFoundError", "message": "No module named 'theauditor.docker_analyzer'"}}

```

---

### Failure 12: `aud graphql`

- **Phase:** invoke
- **Exit Code:** 2
- **Duration:** 0.63s

**Stderr (last 1500 chars):**
```python


```

---


## Test Coverage Summary

| Phase | Total | Passed | Failed |
|-------|-------|--------|--------|
| Help (--help) | 77 | 77 | 0 |
| Invocation | 37 | 25 | 12 |


## Skipped Commands (By Design)

These commands were not tested with real invocations:

- `aud detect-patterns`: Long running analysis (30+ seconds)
- `aud full`: Heavy pipeline - runs 20+ phases, too slow for smoke test
- `aud setup-ai`: Installs packages and creates venv - modifies environment