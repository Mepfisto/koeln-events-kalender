from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from zoneinfo import ZoneInfo

from src.rules import EventRuleEngine

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("koeln-calendar")
USER_AGENT = (
    "KoelnEventsCalendar/2.0 "
    "(+https://github.com/Mepfisto/koeln-events-kalender)"
)
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    }
)


@dataclass
class Event:
    title: str
    start: str
    end: str
    location: str = ""
    category: str = ""
    url: str = ""
    description: str = ""
    source: str = ""

    @property
    def key(self) -> str:
        normalized_title = re.sub(r"\W+", "", self.title.casefold())
        return f"{normalized_title}|{self.start[:10]}"


def get(url: str, timeout: int = 25) -> str:
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            LOG.warning(
                "Abruf fehlgeschlagen (%s/3): %s – %s",
                attempt + 1,
                url,
                exc,
            )
            time.sleep(2**attempt)

    raise RuntimeError(f"Quelle nicht erreichbar: {url}") from last_error


def flatten_jsonld(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from flatten_jsonld(item)
    elif isinstance(value, dict):
        if "@graph" in value:
            yield from flatten_jsonld(value["@graph"])
        yield value


def clean_text(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        BeautifulSoup(str(value or ""), "html.parser").get_text(" "),
    ).strip()


def parse_location(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)

    if isinstance(value, list):
        return " / ".join(
            part
            for part in (parse_location(item) for item in value)
            if part
        )

    if isinstance(value, dict):
        name = clean_text(value.get("name", ""))
        address = value.get("address", "")

        if isinstance(address, dict):
            address = " ".join(
                clean_text(part)
                for part in (
                    address.get("streetAddress", ""),
                    address.get("postalCode", ""),
                    address.get("addressLocality", ""),
                )
                if part
            )

        address = clean_text(address)
        return ", ".join(part for part in (name, address) if part)

    return ""


def normalize_datetime(value: Any) -> str:
    if not value:
        return ""

    try:
        parsed = dateparser.isoparse(str(value).strip())
    except (TypeError, ValueError):
        return ""

    if isinstance(parsed, datetime):
        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=ZoneInfo("Europe/Berlin")
            )
        return parsed.isoformat()

    return str(parsed)


def inferred_end(start: str) -> str:
    if "T" in start:
        return (
            dateparser.isoparse(start) + timedelta(hours=2)
        ).isoformat()

    return (
        date.fromisoformat(start) + timedelta(days=1)
    ).isoformat()


def parse_jsonld_events(
    page_html: str,
    page_url: str,
    default_category: str,
    source: str,
) -> list[Event]:
    soup = BeautifulSoup(page_html, "html.parser")
    found: list[Event] = []

    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()

        if not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(html.unescape(raw).strip())
            except json.JSONDecodeError:
                continue

        for obj in flatten_jsonld(data):
            raw_type = obj.get("@type", "")
            types = raw_type if isinstance(raw_type, list) else [raw_type]

            if "Event" not in types:
                continue

            name = clean_text(obj.get("name", ""))
            start = normalize_datetime(obj.get("startDate"))

            if not name or not start:
                continue

            end = (
                normalize_datetime(obj.get("endDate"))
                or inferred_end(start)
            )
            category = clean_text(
                obj.get("eventType")
                or obj.get("genre")
                or obj.get("category")
                or default_category
            )
            event_url = obj.get("url") or page_url

            found.append(
                Event(
                    title=name,
                    start=start,
                    end=end,
                    location=parse_location(obj.get("location")),
                    category=category,
                    url=urljoin(page_url, str(event_url)),
                    description=clean_text(
                        obj.get("description", "")
                    )[:1200],
                    source=source,
                )
            )

    return found


def discover_links(
    page_html: str,
    base_url: str,
    patterns: list[str],
    maximum: int,
) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        url = urljoin(
            base_url,
            anchor.get("href", ""),
        ).split("#", 1)[0]
        parsed = urlparse(url)

        if parsed.netloc != base_domain:
            continue
        if not any(pattern in parsed.path for pattern in patterns):
            continue
        if url.rstrip("/") == base_url.rstrip("/") or url in seen:
            continue

        seen.add(url)
        links.append(url)

        if len(links) >= maximum:
            break

    return links


def scrape_source(config: dict[str, Any]) -> list[Event]:
    source_name = config["name"]
    url = config["url"]
    category = config.get("category", "")

    page = get(url)
    events = parse_jsonld_events(
        page,
        url,
        category,
        source_name,
    )

    if config.get("mode") != "crawl_event_links":
        return events

    links = discover_links(
        page,
        url,
        config.get("link_patterns", ["/event/"]),
        int(config.get("max_detail_pages", 60)),
    )
    LOG.info("%s: %d Detailseiten gefunden", source_name, len(links))

    for index, link in enumerate(links, start=1):
        try:
            detail = get(link)
            events.extend(
                parse_jsonld_events(
                    detail,
                    link,
                    category,
                    source_name,
                )
            )
        except Exception as exc:
            LOG.warning(
                "Detailseite übersprungen: %s (%s)",
                link,
                exc,
            )

        if index % 20 == 0:
            time.sleep(1)

    return events


def load_manual_events() -> list[Event]:
    path = ROOT / "data" / "manual_events.json"

    if not path.exists():
        return []

    return [
        Event(**item)
        for item in json.loads(
            path.read_text(encoding="utf-8")
        )
    ]


def within_window(
    event: Event,
    past_days: int,
    future_days: int,
) -> bool:
    try:
        event_date = dateparser.isoparse(event.start).date()
    except (TypeError, ValueError):
        return False

    today = datetime.now(
        ZoneInfo("Europe/Berlin")
    ).date()

    return (
        today - timedelta(days=past_days)
        <= event_date
        <= today + timedelta(days=future_days)
    )


def deduplicate(events: Iterable[Event]) -> list[Event]:
    chosen: dict[str, Event] = {}

    for event in events:
        current = chosen.get(event.key)

        if current is None:
            chosen[event.key] = event
            continue

        new_score = (
            len(event.description)
            + len(event.location)
            + (100 if event.url else 0)
        )
        old_score = (
            len(current.description)
            + len(current.location)
            + (100 if current.url else 0)
        )

        if new_score > old_score:
            chosen[event.key] = event

    return sorted(
        chosen.values(),
        key=lambda item: item.start,
    )


def apply_rules(
    events: list[Event],
    rule_config: dict[str, Any],
) -> tuple[list[Event], list[dict[str, Any]]]:
    engine = EventRuleEngine()
    accepted: list[Event] = []
    report: list[dict[str, Any]] = []

    for event in events:
        decision = engine.decide(event, rule_config)

        report.append(
            {
                "title": event.title,
                "source": event.source,
                "included": decision.include,
                "reason": decision.reason,
            }
        )

        if decision.include:
            accepted.append(event)

    return accepted, report


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def fold(line: str) -> str:
    if len(line.encode("utf-8")) <= 73:
        return line

    pieces: list[str] = []
    current = ""

    for character in line:
        candidate = current + character

        if len(candidate.encode("utf-8")) > 73:
            pieces.append(current)
            current = " " + character
        else:
            current = candidate

    pieces.append(current)
    return "\r\n".join(pieces)


def ics_datetime(value: str) -> tuple[str, str]:
    # Ein Wert ohne Uhrzeit ist ein ganztägiges Ereignis.
    if "T" not in value:
        parsed_date = date.fromisoformat(value)
        return "VALUE=DATE", parsed_date.strftime("%Y%m%d")

    parsed = dateparser.isoparse(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=ZoneInfo("Europe/Berlin")
        )

    return (
        "",
        parsed.astimezone(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
    )


def build_ics(events: list[Event], name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Koeln Events Rule Engine//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(name)}",
        "X-WR-TIMEZONE:Europe/Berlin",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]

    for event in events:
        start_parameter, start_value = ics_datetime(event.start)
        end_parameter, end_value = ics_datetime(event.end)
        uid = (
            hashlib.sha256(
                event.key.encode("utf-8")
            ).hexdigest()[:32]
            + "@koeln-events"
        )
        description = event.description

        if event.source:
            description += f"\nQuelle: {event.source}"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                (
                    f"DTSTART"
                    f"{';' + start_parameter if start_parameter else ''}"
                    f":{start_value}"
                ),
                (
                    f"DTEND"
                    f"{';' + end_parameter if end_parameter else ''}"
                    f":{end_value}"
                ),
                f"SUMMARY:{ics_escape(event.title)}",
                f"LOCATION:{ics_escape(event.location)}",
                (
                    "DESCRIPTION:"
                    f"{ics_escape(description.strip())}"
                ),
                f"CATEGORIES:{ics_escape(event.category)}",
                f"URL:{event.url}",
                "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return (
        "\r\n".join(fold(line) for line in lines)
        + "\r\n"
    )


def render_index(
    events: list[Event],
    status: dict[str, Any],
) -> str:
    items = "\n".join(
        (
            f"<li><strong>{html.escape(event.title)}</strong>"
            f" – {html.escape(event.start[:10])}"
            + (
                f" – {html.escape(event.location)}"
                if event.location
                else ""
            )
            + "</li>"
        )
        for event in events[:150]
    )

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Köln – Straßenfeste, Bier- &amp; Weinfeste</title>
<style>
body{{font:16px system-ui;max-width:850px;margin:40px auto;padding:0 18px;line-height:1.5}}
a.button{{display:inline-block;padding:10px 14px;border:1px solid;border-radius:8px;text-decoration:none}}
small{{color:#555}}
</style>
</head>
<body>
<h1>Köln – Straßenfeste, Bier- &amp; Weinfeste</h1>
<p><a class="button" href="koeln-events.ics">ICS-Kalender abonnieren/herunterladen</a></p>
<p>{len(events)} ausgewählte Termine. Zuletzt erzeugt: {html.escape(status["generated_at"])}</p>
<p><small>Termine vor dem Besuch auf der Originalquelle prüfen.</small></p>
<ul>{items}</ul>
</body>
</html>
"""


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    config = json.loads(
        (ROOT / "sources.json").read_text(
            encoding="utf-8"
        )
    )
    all_events = load_manual_events()
    failures: list[str] = []

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue

        try:
            scraped = scrape_source(source)
            LOG.info(
                "%s: %d Event-Datensätze gelesen",
                source["name"],
                len(scraped),
            )
            all_events.extend(scraped)
        except Exception as exc:
            message = f'{source["name"]}: {exc}'
            failures.append(message)
            LOG.error("%s", message)

    dated_events = [
        event
        for event in all_events
        if within_window(
            event,
            past_days=7,
            future_days=int(config["look_ahead_days"]),
        )
    ]

    filtered_events, filter_report = apply_rules(
        dated_events,
        config.get("rules", {}),
    )
    events = deduplicate(filtered_events)

    LOG.info(
        "Regel-Engine: %d von %d Terminen übernommen",
        len(events),
        len(dated_events),
    )

    if not events:
        LOG.error(
            "Keine passenden Termine; bestehende "
            "Kalenderdatei wird nicht überschrieben."
        )
        return 2

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    (docs / "koeln-events.ics").write_text(
        build_ics(events, config["calendar_name"]),
        encoding="utf-8",
        newline="",
    )
    (docs / "events.json").write_text(
        json.dumps(
            [asdict(event) for event in events],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (docs / "filter-report.json").write_text(
        json.dumps(
            filter_report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    status = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "event_count": len(events),
        "events_before_filter": len(dated_events),
        "source_failures": failures,
    }

    (docs / "status.json").write_text(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (docs / "index.html").write_text(
        render_index(events, status),
        encoding="utf-8",
    )

    LOG.info("Fertig: %d eindeutige Termine", len(events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
