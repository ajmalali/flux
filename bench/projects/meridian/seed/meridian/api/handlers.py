"""HTTP-shaped handlers over the service layer.

Thin by rule (CLAUDE.md): parse, delegate, serialise. No booking rule may be
decided here.
"""

from ..errors import MeridianError, NotFound, ValidationError
from ..store.repositories import to_iso
from .router import Response


def space_json(space):
    return {"id": space.id, "name": space.name, "capacity": space.capacity,
            "hourly_cents": space.hourly_cents,
            "open_hour": space.open_hour, "close_hour": space.close_hour}


def booking_json(booking):
    return {"id": booking.id, "space_id": booking.space_id, "member_id": booking.member_id,
            "start": to_iso(booking.start), "end": to_iso(booking.end),
            "price_cents": booking.price_cents, "status": booking.status,
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

    router.get("/spaces", list_spaces)
    router.get("/spaces/{space_id}", get_space)
    router.get("/spaces/{space_id}/bookings", list_space_bookings)
    router.get("/bookings/{booking_id}", get_booking)
    router.post("/bookings/{booking_id}/cancel", cancel_booking)
    return router
