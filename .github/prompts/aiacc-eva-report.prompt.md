---
name: aiacc-eva-report
scope: ai-accounting-copilot
version: 2026-06-10
---

# /aiacc-eva-report

Run AI accounting evaluation report generator against expectations answer keys.

## Command Options
1. `/aiacc-eva-report -jsonanswer`
2. `/aiacc-eva-report -full-report`
3. `/aiacc-eva-report -comp-report <comp id>/<comp name>`

## Required Behavior
- When option is `-jsonanswer`, run:
```powershell
python scripts/eva_report.py -jsonanswer
```

- When option is `-full-report`, run:
```powershell
python scripts/eva_report.py -full-report
```

- When option is `-comp-report <comp>`, run:
```powershell
python scripts/eva_report.py -comp-report <comp>
```

## Important Notes
- `-full-report` and `-comp-report` call live API `http://127.0.0.1:8000/api/process`.
- Ensure backend service is running before live modes.

## Report Back
Return:
- output HTML path
- output JSON path
- summary sample size and per-field accuracy lines
