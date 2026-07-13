"""Fail closed when a Python process under test attempts network access."""

from __future__ import annotations

import socket


class NetworkAccessDenied(RuntimeError):
    pass


def _deny(*_args, **_kwargs):
    raise NetworkAccessDenied("network access is disabled in skill tests")


class _DeniedSocket(socket.socket):
    connect = _deny
    connect_ex = _deny
    # UDP and raw datagrams go out without connect() — deny them explicitly.
    sendto = _deny
    sendmsg = _deny


socket.socket = _DeniedSocket
socket.create_connection = _deny
socket.getaddrinfo = _deny
