# Backend dependency security audit (pip-audit)

**Project:** BottleCRM backend (Django-CRM-198310/backend)  
**Audit tool:** pip-audit 2.10.0  
**Python:** 3.12  
**Input:** `backend/requirements.txt`  
**Command(s):**
- `python -m pip_audit -r requirements.txt`
- `python -m pip_audit -r requirements.txt -f json`

## Results summary (grouped by severity)

- **Critical:** 0
- **High:** 0
- **Medium:** 0
- **Low:** 0

## Detailed findings

`pip-audit` output: **No known vulnerabilities found**.

No CVE/GHSA identifiers, severities/CVSS scores, affected versions, or fixed-version recommendations were produced for this audit run.

## Notes / recommendations

- Re-run this audit regularly (e.g., monthly) and after any dependency changes.
- Consider pinning currently unpinned packages (e.g., `python-dateutil`, `weasyprint`, `cairocffi`, `gunicorn`) to improve reproducibility and make audits easier to compare over time.
- Optionally add `pip-audit` to CI and fail builds on findings.
