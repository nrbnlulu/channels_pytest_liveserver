import threading
import time

import pytest

from functools import partial

import websockets
from daphne.testing import DaphneProcess
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.utils import modify_settings

from daphne.server import Server as DaphneServer
from daphne.endpoints import build_endpoint_description_strings


def make_application(*, static_wrapper):
    # Module-level function for pickle-ability
    from app.app.asgi import application

    if static_wrapper is not None:
        application = static_wrapper(application)
    return application


class ChannelsLiveServerProc:
    host = "localhost"
    ProtocolServerProcess = DaphneProcess
    static_wrapper = ASGIStaticFilesHandler
    serve_static = True

    def __init__(self) -> None:
        for connection in connections.all():
            if connection.vendor == "sqlite" and connection.is_in_memory_db():
                raise ImproperlyConfigured(
                    "ChannelsLiveServer can not be used with in memory databases"
                )

        self._live_server_modified_settings = modify_settings(
            ALLOWED_HOSTS={"append": self.host}
        )
        self._live_server_modified_settings.enable()

        get_application = partial(
            make_application,
            static_wrapper=self.static_wrapper if self.serve_static else None,
        )

        self._server_process = self.ProtocolServerProcess(self.host, get_application)
        self._server_process.start()
        self._server_process.ready.wait()
        self._port = self._server_process.port.value

    def stop(self) -> None:
        self._server_process.terminate()
        self._server_process.join()
        self._live_server_modified_settings.disable()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self._port}"

    @property
    def http_url(self):
        return f"http://{self.host}:{self._port}"


@pytest.fixture
def channels_live_server_proc(request):
    server = ChannelsLiveServerProc()
    request.addfinalizer(server.stop)
    return server


def get_open_port() -> int:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


class ChannelsLiveServerThread:
    host = "localhost"
    static_wrapper = ASGIStaticFilesHandler
    serve_static = True

    def __init__(self) -> None:
        self.port = get_open_port()
        for connection in connections.all():
            if connection.vendor == "sqlite" and connection.is_in_memory_db():
                raise ImproperlyConfigured(
                    "ChannelsLiveServer can not be used with in memory databases"
                )

        self._live_server_modified_settings = modify_settings(
            ALLOWED_HOSTS={"append": self.host}
        )
        self._live_server_modified_settings.enable()

        get_application = partial(
            make_application,
            static_wrapper=self.static_wrapper if self.serve_static else None,
        )
        endpoints = build_endpoint_description_strings(host=self.host, port=self.port)

        self._server = DaphneServer(application=get_application(), endpoints=endpoints)
        t = threading.Thread(target=self._server.run)
        t.start()
        for _ in range(10):
            time.sleep(0.10)
            if self._server.listening_addresses:
                break
        assert self._server.listening_addresses[0]

    def stop(self) -> None:
        self._server.stop()
        self._live_server_modified_settings.disable()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    @property
    def http_url(self):
        return f"http://{self.host}:{self.port}"


@pytest.fixture(scope="session", autouse=True)
def channels_live_server_thread(request):
    server = ChannelsLiveServerThread()
    request.addfinalizer(server.stop)
    return server


async def test_ws_proc(channels_live_server_proc, db):
    async with websockets.connect(channels_live_server_proc.url) as ws:
        await ws.send("hello")
        res = await ws.recv()
        assert res == "hello"


async def test_ws_thread(channels_live_server_thread, db):
    async with websockets.connect(channels_live_server_thread.url) as ws:
        await ws.send("hello")
        res = await ws.recv()
        assert res == "hello"
