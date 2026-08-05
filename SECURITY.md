# Security Policy

## Educational use

This system is built for educational purposes. It is **not** a medical device
and must not be used for clinical decision-making.

## Reporting a vulnerability

If you discover a security issue, please open a GitHub issue with the
`security` label or contact the maintainer directly via email. Do **not**
include exploit details in public issues until a fix is available.

## Scope

In-scope concerns:

- Authentication / authorization bypasses
- SQL injection (parameterized queries — verify before reporting)
- Cross-site scripting (template autoescaping — verify)
- Insecure session / cookie defaults
- Model integrity (artifacts tampering)

Out of scope:

- Clinical correctness of predictions (see MODEL_CARD.md)
- Theoretical risk of patient re-identification from the public dataset

## Supported versions

| version | supported           |
|---------|---------------------|
| 1.0.x   | ✅ active           |