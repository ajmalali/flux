# Meridian

A booking service for co-working spaces. Members book rooms by the hour; the
service quotes a price, records the booking, and reports on how well each space
is used.

Standard library only — no dependencies, no build step.

```
python3 -m unittest discover -s tests     # the gate
python3 -m meridian.cli spaces            # list spaces
python3 -m meridian.cli book --space s-focus --member m-ada --start 2026-09-01T10:00 --hours 2
```

## Layout

    meridian/domain/     pure rules: intervals, pricing, availability. No I/O.
    meridian/store/      JSON-file persistence. Knows nothing about rules.
    meridian/service/    orchestration: the only layer allowed to touch both.
    meridian/api/        a tiny router over the service layer.
    meridian/cli.py      a thin command line over the service layer.

Data lives in a single JSON file (`meridian-data.json` by default), written
atomically. `meridian/clock.py` exists so nothing calls `datetime.now()` directly
and every test is deterministic.
