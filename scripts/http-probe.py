#!/usr/bin/env python3
"""
RTK-safe HTTP probe: replaces `curl URL | ...` pipelines in skills.
When a CLI proxy (e.g. RTK / Rust Token Killer) intercepts curl, it may
summarise the response before the pipe consumer sees it, causing grep/jq/wc
to operate on the summary rather than the raw HTTP body. Using urllib.request
directly bypasses the proxy entirely and guarantees the raw response reaches
the caller.
"""

import argparse
import sys
import urllib.request
import urllib.error


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Minimal HTTP probe using urllib (RTK-safe curl replacement)."
    )
    p.add_argument("url", help="Target URL")
    p.add_argument(
        "--status", action="store_true",
        help="Print only the HTTP status code to stdout; catch 4xx/5xx without error exit"
    )
    p.add_argument(
        "--head", action="store_true",
        help="Print status line + response headers, no body (like curl -I)"
    )
    p.add_argument(
        "--timeout", type=float, default=5,
        metavar="N", help="Timeout in seconds (default: 5)"
    )
    p.add_argument(
        "--method", default="GET",
        metavar="METHOD", help="HTTP method (default: GET)"
    )
    p.add_argument(
        "--header", action="append", default=[],
        metavar="Name: Value", dest="headers",
        help="Request header (repeatable)"
    )
    return p


def parse_headers(raw: list) -> dict:
    result = {}
    for h in raw:
        if ":" not in h:
            print(f"Warning: ignoring malformed header: {h!r}", file=sys.stderr)
            continue
        name, _, value = h.partition(":")
        result[name.strip()] = value.strip()
    return result


def run(args) -> int:
    req = urllib.request.Request(
        args.url,
        method=args.method,
        headers=parse_headers(args.headers),
    )

    def _print_head(code: int, headers) -> None:
        print(f"HTTP/1.1 {code}")
        for k, v in headers.items():
            print(f"{k}: {v}")

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            code = resp.status
            if args.status:
                print(code)
                return 0
            if args.head:
                _print_head(code, resp.headers)
                return 0
            # Body mode — write raw bytes to stdout.buffer to preserve binary
            body = resp.read()
            try:
                sys.stdout.write(body.decode("utf-8"))
            except UnicodeDecodeError:
                sys.stdout.buffer.write(body)
            return 0

    except urllib.error.HTTPError as e:
        # 4xx / 5xx: in --status / --head mode, report the code without failing
        if args.status:
            print(e.code)
            return 0
        if args.head:
            _print_head(e.code, e.headers)
            return 0
        print(f"HTTP error {e.code}: {e.reason}", file=sys.stderr)
        return e.code if e.code else 1

    except urllib.error.URLError as e:
        print(f"URL error: {e.reason}", file=sys.stderr)
        return 1

    except OSError as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    args = build_parser().parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
