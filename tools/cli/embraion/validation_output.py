"""Bounded reading of validation command output.

The runner lets a command write straight into anonymous temporary files. This
module reads those files back without holding more than the configured amount in
memory: the beginning and the end, cut on line boundaries, plus exact totals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import BinaryIO, Callable

_CHUNK_BYTES = 1024 * 1024
# Wider than the redaction patterns on purpose: any armored private key block counts.
_KEY_BEGIN = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_KEY_END = re.compile(rb"-----END [A-Z ]*PRIVATE KEY-----")


@dataclass(frozen=True)
class CapturedOutput:
    """The kept head (and tail) of one output stream with the size of the whole."""

    head: str = ""
    tail: str = ""
    total_bytes: int = 0
    total_lines: int = 0
    omitted_bytes: int = 0
    omitted_lines: int = 0

    @property
    def truncated(self) -> bool:
        return self.omitted_bytes > 0


def _lines(data: bytes) -> int:
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def _drop_unpaired_key_start(head: bytes) -> bytes:
    """Cut a private key block whose end lies beyond the kept head; redaction needs both markers."""
    begins = list(_KEY_BEGIN.finditer(head))
    if begins and not _KEY_END.search(head, begins[-1].end()):
        return head[: begins[-1].start()]
    return head


def _drop_unpaired_key_end(tail: bytes) -> bytes:
    """Cut a private key block whose start lies before the kept tail."""
    end = _KEY_END.search(tail)
    if end and not _KEY_BEGIN.search(tail, 0, end.start()):
        line_end = tail.find(b"\n", end.end())
        return b"" if line_end < 0 else tail[line_end + 1 :]
    return tail


def capture_stream(
    handle: BinaryIO,
    limit_bytes: int | None,
    encoding: str,
) -> CapturedOutput:
    """Read a stream; keep it whole without a limit, else keep head and tail halves."""
    size = handle.seek(0, 2)
    handle.seek(0)
    total_lines = 0
    last = b""
    while True:
        chunk = handle.read(_CHUNK_BYTES)
        if not chunk:
            break
        total_lines += chunk.count(b"\n")
        last = chunk[-1:]
    if size and last != b"\n":
        total_lines += 1

    if limit_bytes is None or size <= limit_bytes:
        handle.seek(0)
        return CapturedOutput(
            head=handle.read().decode(encoding, errors="replace"),
            total_bytes=size,
            total_lines=total_lines,
        )

    half = max(limit_bytes // 2, 1)
    handle.seek(0)
    head = handle.read(half)
    cut = head.rfind(b"\n")
    if cut >= 0:
        head = head[: cut + 1]
    handle.seek(size - half)
    tail = handle.read(half)
    handle.seek(size - half - 1)
    if handle.read(1) != b"\n":
        cut = tail.find(b"\n")
        if cut >= 0:
            tail = tail[cut + 1 :]
    head = _drop_unpaired_key_start(head)
    tail = _drop_unpaired_key_end(tail)
    return CapturedOutput(
        head=head.decode(encoding, errors="replace"),
        tail=tail.decode(encoding, errors="replace"),
        total_bytes=size,
        total_lines=total_lines,
        omitted_bytes=size - len(head) - len(tail),
        omitted_lines=max(total_lines - _lines(head) - _lines(tail), 0),
    )


def truncation_marker(captured: CapturedOutput) -> str:
    return (
        f"[... output truncated: {captured.omitted_bytes} bytes "
        f"({captured.omitted_lines} lines) omitted; "
        f"total {captured.total_bytes} bytes, {captured.total_lines} lines ...]"
    )


def render_output(captured: CapturedOutput, scrub: Callable[[str], str]) -> str:
    """Return redacted text; head and tail are scrubbed apart, then joined by the marker."""
    head = scrub(captured.head)
    if not captured.truncated:
        return head
    separator = "" if not head or head.endswith("\n") else "\n"
    return f"{head}{separator}{truncation_marker(captured)}\n{scrub(captured.tail)}"
