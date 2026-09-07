from http.server import BaseHTTPRequestHandler

from api.index import handler


def test_vercel_entrypoint_is_an_http_handler() -> None:
    assert issubclass(handler, BaseHTTPRequestHandler)
    assert callable(handler.do_GET)
