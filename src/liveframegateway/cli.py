import argparse

from aiohttp import web

from .service import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="LiveFrameGateway service")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Run the HTTP frame gateway")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8095)
    serve.add_argument("--ring-size", type=int, default=20)
    serve.add_argument("--stale-session-ttl-s", type=float, default=900.0)
    serve.add_argument("--ec-shared-storage-path", default="")
    serve.add_argument("--primer-url", default="")
    serve.add_argument("--primer-timeout-s", type=float, default=5.0)

    args = parser.parse_args()
    if args.command != "serve":
        parser.print_help()
        raise SystemExit(2)

    app = create_app(
        ring_size=args.ring_size,
        stale_session_ttl_s=args.stale_session_ttl_s,
        ec_shared_storage_path=args.ec_shared_storage_path,
        primer_url=args.primer_url,
        primer_timeout_s=args.primer_timeout_s,
    )
    web.run_app(app, host=args.host, port=args.port)
