# Security policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security reports.

Email `security@pressingly.com` with:

- A description of the issue and its impact.
- Steps to reproduce, including a minimal proof-of-concept where possible.
- The version of `askii` you're using (`python -c "import askii; print(askii.__version__)"`).
- Any disclosure timeline constraints on your side.

We'll acknowledge receipt within two business days and aim to ship a fix
(or coordinated disclosure plan) within 30 days for confirmed issues.

## Scope

- Token handling, secret redaction in logs, and request signing.
- Authentication bypass via the client surface or CLI.
- Cache poisoning across users or processes.
- Dependency vulnerabilities surfaced by Dependabot or `pip-audit`.

Out of scope (open an issue instead):

- Bugs in the upstream Askii API itself (report to the API team).
- Misconfiguration in a consumer's own deployment.
