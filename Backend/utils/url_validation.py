import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import AppException


def validate_jira_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise AppException(
            code="INVALID_JIRA_URL", message="Jira URL must use https.", status_code=400
        )
    if not parsed.hostname or not parsed.hostname.endswith(".atlassian.net"):
        raise AppException(
            code="INVALID_JIRA_URL",
            message="Only *.atlassian.net Jira URLs are allowed.",
            status_code=400,
        )
    try:
        resolved_ips = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise AppException(
            code="INVALID_JIRA_URL", message="Could not resolve Jira URL.", status_code=400
        )
    for family, _, _, _, sockaddr in resolved_ips:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_link_local or ip.is_loopback or ip.is_reserved:
            raise AppException(
                code="INVALID_JIRA_URL",
                message="Jira URL resolves to a disallowed address.",
                status_code=400,
            )
