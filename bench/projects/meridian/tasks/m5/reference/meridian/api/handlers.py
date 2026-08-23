"""HTTP-shaped handlers over the service layer.

Thin by rule (CLAUDE.md): parse, delegate, serialise. No booking rule may be
decided here.
"""

from datetime import datetime, timezone

from ..errors import ConflictError, MeridianError, NotFound, ValidationError
from ..service.reporting import utilization, utilization_by_space
from ..store.repositories import from_iso, to_iso
from .router import Response


def parse_day(query):
    """The ``day`` query parameter as a UTC midnight datetime.

    Returns ``(day, None)`` or ``(None, Response)`` -- parsing is the api layer's
    job, so the error shape is decided here and the reporting rule stays in
    ``service``."""
    raw = query.get("day")
    if not raw:
        return None, Response(400, {"error": "query parameter 'day' is required"})
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None, Response(400, {"error": "'day' must be a YYYY-MM-DD date"})
    return parsed.replace(tzinfo=timezone.utc), None


def space_json(space):
    return {"id": space.id, "name": space.name, "capacity": space.capacity,
            "hourly_cents": space.hourly_cents,
            "open_hour": space.open_hour, "close_hour": space.close_hour}


def booking_json(booking):
    return {"id": booking.id, "space_id": booking.space_id, "member_id": booking.member_id,
            "start": to_iso(booking.start), "end": to_iso(booking.end),
            "price_cents": booking.price_cents, "status": booking.status,
            "expires_at": to_iso(booking.expires_at) if booking.expires_at else None,
            "refund_cents": booking.refund_cents, "series_id": booking.series_id,
            "created_at": to_iso(booking.created_at)}


def build_router(service):
    from .router import Router

    repos = service.repos
    router = Router()

    def list_spaces(query, body):
        return Response(200, {"spaces": [space_json(s) for s in repos.spaces.all()]})

    def get_space(space_id, query, body):
        try:
            return Response(200, space_json(repos.spaces.get(space_id)))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})

    def get_booking(booking_id, query, body):
        try:
            return Response(200, booking_json(repos.bookings.get(booking_id)))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})

    def list_space_bookings(space_id, query, body):
        try:
            bookings = service.bookings_for_space(space_id)
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        return Response(200, {"bookings": [booking_json(b) for b in bookings]})

    def cancel_booking(booking_id, query, body):
        try:
            return Response(200, booking_json(service.cancel_booking(booking_id)))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        except ValidationError as exc:
            return Response(409, {"error": str(exc)})
        except MeridianError as exc:
            return Response(400, {"error": str(exc)})

    def get_series(series_id, query, body):
        bookings = repos.bookings.for_series(series_id)
        if not bookings:
            return Response(404, {"error": "no series with id %r" % (series_id,)})
        return Response(200, {"series_id": series_id,
                              "bookings": [booking_json(b) for b in bookings]})

    def space_utilization(space_id, query, body):
        day, error = parse_day(query)
        if error is not None:
            return error
        try:
            percent = utilization(repos, space_id, day)
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        return Response(200, {"space_id": space_id, "day": query["day"], "percent": percent})

    def all_utilization(query, body):
        day, error = parse_day(query)
        if error is not None:
            return error
        return Response(200, {"day": query["day"],
                              "spaces": utilization_by_space(repos, day)})

    def take_hold(space_id, query, body):
        payload = body or {}
        try:
            start = _moment(payload.get("start"))
            end = _moment(payload.get("end"))
        except ValueError as exc:
            return Response(400, {"error": str(exc)})
        try:
            hold = service.hold_space(space_id, payload.get("member_id"), start, end,
                                      minutes=payload.get("minutes", 15))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        except ConflictError as exc:
            return Response(409, {"error": str(exc)})
        except MeridianError as exc:
            return Response(400, {"error": str(exc)})
        return Response(201, booking_json(hold))

    def confirm_hold(booking_id, query, body):
        try:
            return Response(200, booking_json(service.confirm_hold(booking_id)))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        except ConflictError as exc:
            return Response(409, {"error": str(exc)})
        except MeridianError as exc:
            return Response(400, {"error": str(exc)})

    def release_hold(booking_id, query, body):
        try:
            return Response(200, booking_json(service.release_hold(booking_id)))
        except NotFound as exc:
            return Response(404, {"error": str(exc)})
        except MeridianError as exc:
            return Response(400, {"error": str(exc)})

    router.get("/spaces", list_spaces)
    router.get("/utilization", all_utilization)
    router.get("/spaces/{space_id}/utilization", space_utilization)
    router.get("/spaces/{space_id}", get_space)
    router.get("/spaces/{space_id}/bookings", list_space_bookings)
    router.get("/bookings/{booking_id}", get_booking)
    router.get("/series/{series_id}", get_series)
    router.post("/bookings/{booking_id}/cancel", cancel_booking)
    router.post("/spaces/{space_id}/holds", take_hold)
    router.post("/holds/{booking_id}/confirm", confirm_hold)
    router.post("/holds/{booking_id}/release", release_hold)
    return router


def _moment(text):
    """An ISO-8601 instant from the wire, or a message the caller can act on."""
    if not text:
        raise ValueError("start and end are required ISO-8601 datetimes")
    try:
        return from_iso(text)
    except (TypeError, ValueError):
        raise ValueError("%r is not an ISO-8601 datetime" % (text,))
