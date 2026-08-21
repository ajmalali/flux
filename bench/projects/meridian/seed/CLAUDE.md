# Meridian — conventions

These are binding. Code that ignores them will be rejected in review even if the
tests pass.

- **Standard library only.** No third-party packages, ever.
- **Layering is one-directional**: `domain` knows nothing about `store`, `service`
  or `api`. `store` knows nothing about `domain` rules. `service` is the only layer
  allowed to use both. `api` and `cli` are thin — they parse input, call `service`,
  and format output. Business rules never live in `api`, `cli` or `store`.
- **`domain` is pure.** No file access, no clock reads, no randomness. Anything
  time-dependent takes the time as an argument.
- **Never call `datetime.now()` directly.** Take a `Clock` (see `meridian/clock.py`)
  and call `clock.now()`, so tests can pin time.
- **Money is integer cents.** Never floats. Rounding is explicit at the point it
  happens.
- **Times are timezone-aware UTC `datetime` objects** in memory, ISO-8601 strings
  on disk. Intervals are half-open: `[start, end)`.
- **Errors**: raise the types in `meridian/errors.py`. Never raise bare
  `Exception`, never return `None` to signal failure.
- Every behaviour change ships with tests in `tests/`.
- Gate: `python3 -m unittest discover -s tests`
