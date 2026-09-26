"""Strict official-source retrieval and project-configured SKU parsing."""

from __future__ import annotations

import hashlib
import html
import http.client
import ipaddress
import re
import socket
import ssl
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any


OFFICIAL_HOSTS = {
    "openai": {"developers.openai.com"},
    "anthropic": {"platform.claude.com"},
    "gemini": {"ai.google.dev"},
    "deepseek": {"api-docs.deepseek.com"},
}
MAX_RESPONSE_BYTES = 1_500_000


def validate_official_url(url: str, adapter: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS.get(adapter, set())
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.fragment):
        raise RuntimeError("Pricing URL is not an approved official HTTPS source.")


def approved_url(url: str, adapter: str) -> list[str]:
    validate_official_url(url, adapter)
    parsed = urllib.parse.urlsplit(url)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise RuntimeError("Could not resolve official pricing host.") from error
    if not addresses or any(
        not ipaddress.ip_address(item[4][0]).is_global for item in addresses
    ):
        raise RuntimeError("Pricing source resolves to a non-public address.")
    return list(dict.fromkeys(item[4][0] for item in addresses))


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, timeout: float) -> None:
        super().__init__(hostname, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def fetch_official(config: dict[str, Any], timeout: float = 15.0) -> bytes:
    url = str(config["url"])
    addresses = approved_url(url, str(config["adapter"]))
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    last_error: OSError | None = None
    for address in addresses:
        connection = _PinnedHTTPS(parsed.hostname or "", address, timeout)
        try:
            connection.request("GET", path, headers={"User-Agent": "EmbrAIon-pricing-refresh/1",
                                                     "Accept": "text/html,text/plain,text/markdown,application/json"})
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise RuntimeError("Pricing source redirected; approve the new official URL explicitly.")
            if response.status != 200:
                raise RuntimeError("Official pricing source returned an unsuccessful status.")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain", "text/markdown", "application/json"}:
                raise RuntimeError("Official pricing source returned an unsupported content type.")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_RESPONSE_BYTES:
                raise RuntimeError("Official pricing response exceeds size limit.")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except OSError as error:
            last_error = error
        finally:
            connection.close()
    else:
        raise RuntimeError("Official pricing source could not be fetched.") from last_error
    if len(body) > MAX_RESPONSE_BYTES or not body:
        raise RuntimeError("Official pricing response is empty or exceeds size limit.")
    return body


def fetch_and_parse(source_id: str, config: dict[str, Any], body: bytes | None = None) -> list[dict[str, Any]]:
    """Parse only exact configured SKU/rate captures; ambiguity aborts refresh."""
    try:
        import regex as bounded_regex
    except ImportError as error:
        raise RuntimeError("Bounded pricing parser dependency is unavailable for refresh.") from error
    if body is None:
        body = fetch_official(config)
    else:
        # Fixtures use the same URL and source validation as live refresh.
        validate_official_url(str(config["url"]), str(config["adapter"]))
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Official pricing response exceeds size limit.")
    try:
        page = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise RuntimeError("Official pricing source is not UTF-8.") from error
    if "<html" in page[:1000].lower() or "<!doctype html" in page[:1000].lower():
        class VisibleText(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self.hidden = 0

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag in {"script", "style"}:
                    self.hidden += 1

            def handle_endtag(self, tag: str) -> None:
                if tag in {"script", "style"} and self.hidden:
                    self.hidden -= 1

            def handle_data(self, value: str) -> None:
                if not self.hidden and value.strip():
                    self.parts.append(value.strip())

        visible = VisibleText()
        visible.feed(page)
        page = " ".join(visible.parts)
    page = re.sub(r"\s+", " ", html.unescape(page))
    from decimal import Decimal, InvalidOperation

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source_digest = hashlib.sha256(body).hexdigest()
    entries: list[dict[str, Any]] = []
    def extract(patterns: dict[str, str], deployment: str, lane: str) -> dict[str, str]:
        rates: dict[str, str] = {}
        for category, expression in patterns.items():
            if len(expression) > 2048:
                raise RuntimeError(f"Pricing pattern for {deployment}.{lane}.{category} exceeds length limit.")
            try:
                matches = list(bounded_regex.finditer(expression, page,
                                                       flags=bounded_regex.IGNORECASE | bounded_regex.DOTALL,
                                                       timeout=2.0))
            except (bounded_regex.error, TimeoutError) as error:
                raise RuntimeError(f"Invalid or timed-out pricing pattern for {deployment}.{lane}.{category}.") from error
            if len(matches) != 1 or "rate" not in matches[0].groupdict():
                raise RuntimeError(f"Pricing source has no unique {deployment}.{lane}.{category} rate.")
            raw = matches[0].group("rate").replace(",", "").strip()
            try:
                amount = Decimal(raw)
            except InvalidOperation as error:
                raise RuntimeError(f"Malformed pricing rate for {deployment}.{lane}.{category}.") from error
            if not amount.is_finite() or amount < 0:
                raise RuntimeError(f"Invalid pricing rate for {deployment}.{lane}.{category}.")
            rates[category] = str(amount)
        return rates

    for deployment, spec in config["skus"].items():
        rates = extract(spec["patterns"], deployment, "standard")
        entry: dict[str, Any] = {
            "deployment": deployment, "sku": spec["sku"], "sourceId": source_id,
            "sourceUrl": config["url"], "sourceDigest": source_digest,
            "retrievedUtc": now, "verifiedUtc": now, "currency": config["currency"],
            "unitTokens": 1_000_000, "rates": rates,
        }
        for optional in ("effectiveDate", "validThrough", "maxInputTokens"):
            if optional in spec:
                entry[optional] = spec[optional]
        if "batchPatterns" in spec:
            entry["batch"] = extract(spec["batchPatterns"], deployment, "batch")
        if "discountPatterns" in spec:
            entry["discounts"] = {name: extract(patterns, deployment, name)
                                  for name, patterns in spec["discountPatterns"].items()}
        if "schedule" in spec:
            schedule = spec["schedule"]
            entry["schedule"] = {"kind": schedule["kind"], "peakUtcHours": schedule["peakUtcHours"],
                                 "peak": extract(schedule["peakPatterns"], deployment, "peak"),
                                 "offPeak": extract(schedule["offPeakPatterns"], deployment, "off-peak")}
            if "holidaysUnverified" in schedule:
                entry["schedule"]["holidaysUnverified"] = schedule["holidaysUnverified"]
        entries.append(entry)
    return entries
