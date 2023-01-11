"""
ASGI config for app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
from channels.generic.websocket import WebsocketConsumer
from channels.routing import URLRouter, ProtocolTypeRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class WsEcho(WebsocketConsumer):

    def websocket_receive(self, message):
        super().websocket_receive(message)

    def receive(self,  text_data=None, bytes_data=None):
        UserModel.objects.all().count()
        self.send(text_data=text_data)


django_application = get_asgi_application()
application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [re_path("^", django_application)]  # type: ignore
        ),  # type: ignore
        "websocket": AuthMiddlewareStack(WsEcho()),
    }
)
