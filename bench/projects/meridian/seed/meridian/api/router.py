"""A router small enough to read in one sitting.

Patterns use ``{name}`` segments: ``/spaces/{space_id}/bookings``. Handlers get
the captured segments as keyword arguments plus a ``query`` dict, and return a
:class:`Response`. No framework, no middleware, no magic.
"""

from dataclasses import dataclass, field


@dataclass
class Response(object):
    status: int
    body: object = None
    headers: dict = field(default_factory=dict)


class Router(object):
    def __init__(self):
        self._routes = []

    def add(self, method, pattern, handler):
        self._routes.append((method.upper(), _segments(pattern), handler))
        return self

    def get(self, pattern, handler):
        return self.add("GET", pattern, handler)

    def post(self, pattern, handler):
        return self.add("POST", pattern, handler)

    def dispatch(self, method, path, query=None, body=None):
        path_parts = _segments(path)
        matched_path = False
        for route_method, pattern, handler in self._routes:
            captured = _match(pattern, path_parts)
            if captured is None:
                continue
            matched_path = True
            if route_method != method.upper():
                continue
            return handler(query=dict(query or {}), body=body, **captured)
        return Response(405 if matched_path else 404,
                        {"error": "method not allowed" if matched_path else "not found"})


def _segments(path):
    return [p for p in str(path).split("/") if p]


def _match(pattern, path_parts):
    if len(pattern) != len(path_parts):
        return None
    captured = {}
    for expected, actual in zip(pattern, path_parts):
        if expected.startswith("{") and expected.endswith("}"):
            captured[expected[1:-1]] = actual
        elif expected != actual:
            return None
    return captured
