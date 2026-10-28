"""Optionally serve the bundled contexts. This does not start or modify a broker."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3004)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be 1..65535')
    SimpleHTTPRequestHandler.extensions_map['.jsonld'] = 'application/ld+json'
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path(__file__).resolve().parent / 'contexts'))
    with ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f'Serving bundled contexts on {args.bind}:{args.port}; Ctrl-C stops the server.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
