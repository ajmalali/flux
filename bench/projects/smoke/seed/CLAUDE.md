# slugify — conventions

- Standard library only. No third-party dependencies, ever.
- Public API lives in `slugify/__init__.py`; implementation in `slugify/core.py`.
- Every behaviour change ships with a test in `tests/`.
- Gate: `python3 -m unittest discover -s tests`
