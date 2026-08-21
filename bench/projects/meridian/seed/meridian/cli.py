"""A thin command line over the service layer."""

import argparse
import json
import sys
from datetime import timedelta

from .api.handlers import booking_json, space_json
from .clock import Clock
from .errors import MeridianError
from .service.booking import BookingService
from .service.reporting import utilization
from .store.jsonstore import JsonStore
from .store.repositories import Repositories, from_iso

DEFAULT_DATA = "meridian-data.json"


def build_service(path, clock=None):
    repos = Repositories(JsonStore(path))
    return BookingService(repos, clock or Clock())


def main(argv=None):
    parser = argparse.ArgumentParser(prog="meridian")
    parser.add_argument("--data", default=DEFAULT_DATA)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("spaces")

    book = sub.add_parser("book")
    book.add_argument("--space", required=True)
    book.add_argument("--member", required=True)
    book.add_argument("--start", required=True)
    book.add_argument("--hours", type=float, default=1.0)

    cancel = sub.add_parser("cancel")
    cancel.add_argument("booking_id")

    report = sub.add_parser("utilization")
    report.add_argument("--space", required=True)
    report.add_argument("--day", required=True)

    args = parser.parse_args(argv)
    service = build_service(args.data)
    try:
        if args.command == "spaces":
            _emit([space_json(s) for s in service.repos.spaces.all()])
        elif args.command == "book":
            start = from_iso(args.start)
            booking = service.create_booking(args.space, args.member, start,
                                             start + timedelta(hours=args.hours))
            _emit(booking_json(booking))
        elif args.command == "cancel":
            _emit(booking_json(service.cancel_booking(args.booking_id)))
        elif args.command == "utilization":
            _emit({"space": args.space, "day": args.day,
                   "percent": utilization(service.repos, args.space, from_iso(args.day))})
        else:
            parser.print_help()
            return 2
    except MeridianError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
