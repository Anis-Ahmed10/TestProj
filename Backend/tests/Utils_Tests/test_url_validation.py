"""Unit tests for app/utils/url_validation.py — 100% coverage."""

import socket

import pytest

from app.core.exceptions import AppException
from app.utils.url_validation import validate_jira_url


def test_rejects_non_https_scheme():
    with pytest.raises(AppException) as exc_info:
        validate_jira_url("http://mycompany.atlassian.net")
    assert exc_info.value.code == "INVALID_JIRA_URL"
    assert exc_info.value.status_code == 400


def test_rejects_missing_hostname():
    with pytest.raises(AppException):
        validate_jira_url("https://")


def test_rejects_hostname_not_ending_in_atlassian_net():
    with pytest.raises(AppException):
        validate_jira_url("https://example.com")


def test_rejects_lookalike_hostname_suffix():
    with pytest.raises(AppException):
        validate_jira_url("https://notatlassian.net.evil.com")


def test_raises_when_dns_resolution_fails(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(AppException) as exc_info:
        validate_jira_url("https://mycompany.atlassian.net")
    assert "resolve" in exc_info.value.message.lower()


@pytest.mark.parametrize("ip", ["10.0.0.5", "127.0.0.1", "169.254.1.1", "0.0.0.0"])
def test_rejects_disallowed_resolved_ip(monkeypatch, ip):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(AppException):
        validate_jira_url("https://mycompany.atlassian.net")


def test_accepts_valid_public_resolved_ip(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.3", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert validate_jira_url("https://mycompany.atlassian.net") is None


def test_accepts_multiple_public_ips(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.3", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1", 0, 0, 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert validate_jira_url("https://mycompany.atlassian.net") is None


def test_rejects_if_any_ip_among_several_is_disallowed(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.3", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(AppException):
        validate_jira_url("https://mycompany.atlassian.net")
