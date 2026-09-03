#!/usr/bin/env python3
"""Monitor an ICU pre-registration seat-list page without logging in.

This program only reads the public seat-list page.  It never stores or sends
an ICU Net ID or password.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_URL = "https://course-reg.icu.ac.jp/reg/prereg_clist/ISC.html"
DEFAULT_COURSE = "21342"


class SeatListParser(HTMLParser):
    """Extract table rows from ICU's intentionally minimal HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: Optional[list[str]] = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "tr":
            self._row = []
            self._in_cell = False
        elif tag == "td" and self._row is not None:
            # The page often omits </TD>, so a following TD closes the former.
            self._row.append("")
            self._in_cell = True

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._in_cell and self._row:
            value = " ".join(data.split())
            if value:
                self._row[-1] = (self._row[-1] + " " + value).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._in_cell = False


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "ICU-seat-monitor/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def read_course(html: str, course_number: str) -> tuple[int, str, list[str]]:
    parser = SeatListParser()
    parser.feed(html)
    parser.close()
    for row in parser.rows:
        if row and row[0] == course_number:
            try:
                return int(row[-1]), row[2], row
            except (IndexError, ValueError) as error:
                raise ValueError(f"Could not parse seat count from row: {row}") from error
    raise ValueError(f"Course {course_number} was not found on the seat-list page")


def page_timestamp(html: str) -> str:
    match = re.search(r"as of\s*([0-2]?\d:[0-5]\d:[0-5]\d)", html, re.IGNORECASE)
    return match.group(1) if match else "unknown time"


def load_state(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def send_webhook(url: str, message: str) -> None:
    # "content" works for Discord; "text" works for Slack-compatible hooks.
    payload = json.dumps({"content": message, "text": message}).encode()
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "ICU-seat-monitor/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Webhook returned HTTP {response.status}")


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--course", default=os.getenv("COURSE_NUMBER", DEFAULT_COURSE))
    argument_parser.add_argument("--url", default=os.getenv("COURSE_LIST_URL", DEFAULT_URL))
    argument_parser.add_argument("--state-file", default=os.getenv("STATE_FILE", "state.json"))
    argument_parser.add_argument("--webhook-url", default=os.getenv("WEBHOOK_URL"))
    argument_parser.add_argument(
        "--fail-when-open",
        action="store_true",
        help="Exit with status 1 when a seat is available (useful for Actions email alerts).",
    )
    arguments = argument_parser.parse_args()

    try:
        html = fetch(arguments.url)
        seats, title, _ = read_course(html, arguments.course)
    except (URLError, TimeoutError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    timestamp = page_timestamp(html)
    state_path = Path(arguments.state_file)
    previous = load_state(state_path)
    previous_seats = int(previous.get("seats", 0))
    message = (
        f"ICU seat available: {arguments.course} {title} has {seats} seat(s) left "
        f"(page updated {timestamp} JST)."
    )
    if seats > 0 and previous_seats <= 0:
        print("OPEN: " + message)
        if arguments.webhook_url:
            send_webhook(arguments.webhook_url, message)
    else:
        print(f"{arguments.course}: {seats} seat(s) left (page updated {timestamp} JST).")

    save_state(
        state_path,
        {"course": arguments.course, "seats": seats, "checked_at": timestamp},
    )
    if seats > 0 and arguments.fail_when_open:
        # A scheduled GitHub Actions failure sends a notification to the account
        # that owns and maintains the workflow.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
