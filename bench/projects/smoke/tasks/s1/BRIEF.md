# Add a `max_length` option to `slugify`

`slugify(text, max_length=None)` must gain an optional length cap.

## Required behaviour

- `max_length=None` (the default) keeps today's behaviour exactly.
- When `max_length` is a positive integer, the returned slug is at most that many
  characters.
- If the full slug already fits within `max_length`, it is returned unchanged.
- Otherwise truncation happens **on a word boundary**: keep the longest prefix of
  whole hyphen-separated words that fits within the limit.
- If even the first word does not fit, hard-truncate that word to the limit.
- The result never starts or ends with a hyphen.
- `max_length=0` or a negative value raises `ValueError`.

Worked examples, all for the input `"the quick brown fox"` (full slug
`"the-quick-brown-fox"`, 19 characters):

| `max_length` | result | why |
|---|---|---|
| `19` | `"the-quick-brown-fox"` | fits exactly, returned unchanged |
| `15` | `"the-quick-brown"` | 15 chars, fits exactly on a word boundary |
| `12` | `"the-quick"` | `"the-quick-brown"` is 15, too long; drop back a word |
| `9`  | `"the-quick"` | 9 chars, fits exactly |
| `8`  | `"the"` | `"the-quick"` is 9, too long; drop back a word |
| `2`  | `"th"` | even `"the"` does not fit, so hard-truncate |

And `slugify("supercalifragilistic", max_length=5)` is `"super"`.

## Definition of done

- Implemented in `slugify/core.py`, exported unchanged from `slugify/__init__.py`.
- Covered by new tests in `tests/`.
- `python3 -m unittest discover -s tests` passes.
