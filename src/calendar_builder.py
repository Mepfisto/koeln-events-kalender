from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("koeln-calendar")
USER_AGENT = "KoelnEventsCalendar/1.1 (+public GitHub project; respectful daily fetch)"
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
})

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
        normalized = re.sub(r"\W+", "", self.title.casefold())
        return f"{normalized}|{self.start[:10]}"

def get(url: str, timeout: int = 25) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            LOG.warning("Abruf fehlgeschlagen (%s/3): %s – %s", attempt + 1, url, exc)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Quelle nicht erreichbar: {url}") from last_error

def flatten_jsonld(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from flatten_jsonld(item)
    elif isinstance(value, dict):
        if "@graph" in value:
            yield from flatten_jsonld(value["@graph"])
        yield value

def parse_jsonld_events(page_html: str, page_url: str, default_category: str, source: str) -> list[Event]:
    soup = BeautifulSoup(page_html, "html.parser")
    found: list[Event] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            cleaned = html.unescape(raw).strip()
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                continue
        for obj in flatten_jsonld(data):
            typ = obj.get("@type", "")
            types = typ if isinstance(typ, list) else [typ]
            if "Event" not in types:
                continue
            name = clean_text(obj.get("name", ""))
            start = normalize_datetime(obj.get("startDate"))
            if not name or not start:
                continue
            end = normalize_datetime(obj.get("endDate")) or inferred_end(start)
            location = parse_location(obj.get("location"))
            description = clean_text(obj.get("description", ""))
            event_url = obj.get("url") or page_url
            found.append(Event(
                title=name,
                start=start,
                end=end,
                location=location,
                category=default_category,
                url=urljoin(page_url, str(event_url)),
                description=description[:900],
                source=source,
            ))
    return found

def parse_location(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return " / ".join(filter(None, (parse_location(x) for x in value)))
    if isinstance(value, dict):
        name = clean_text(value.get("name", ""))
        address = value.get("address", "")
        if isinstance(address, dict):
            parts = [
                address.get("streetAddress", ""),
                address.get("postalCode", ""),
                address.get("addressLocality", ""),
            ]
            address = " ".join(clean_text(x) for x in parts if x)
        address = clean_text(address)
        return ", ".join(x for x in [name, address] if x)
    return ""

def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(str(value or ""), "html.parser").get_text(" ")).strip()

def normalize_datetime(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    try:
        parsed = dateparser.isoparse(text)
    except (ValueError, TypeError):
        return ""
    if isinstance(parsed, datetime):
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return parsed.isoformat()
    return str(parsed)

def inferred_end(start: str) -> str:
    if "T" in start:
        return (dateparser.isoparse(start) + timedelta(hours=2)).isoformat()
    return (date.fromisoformat(start) + timedelta(days=1)).isoformat()

def discover_links(page_html: str, base_url: str, patterns: list[str], maximum: int) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        url = urljoin(base_url, anchor.get("href", "")).split("#", 1)[0]
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
    events = parse_jsonld_events(page, url, category, source_name)

    if config.get("mode") == "crawl_event_links":
        links = discover_links(
            page, url,
            config.get("link_patterns", ["/event/"]),
            int(config.get("max_detail_pages", 60)),
        )
        LOG.info("%s: %d Detailseiten gefunden", source_name, len(links))
        for index, link in enumerate(links, 1):
            try:
                detail = get(link)
                events.extend(parse_jsonld_events(detail, link, category, source_name))
            except Exception as exc:
                LOG.warning("Detailseite übersprungen: %s (%s)", link, exc)
            if index % 20 == 0:
                time.sleep(1)
    return events

def load_manual_events() -> list[Event]:
    path = ROOT / "data" / "manual_events.json"
    if not path.exists():
        return []
    return [Event(**item) for item in json.loads(path.read_text(encoding="utf-8"))]

def normalized_search_text(event: Event) -> str:
    return " ".join([
        event.title,
        event.description,
        event.category,
        event.location,
        event.url,
    ]).casefold()

def matches_filters(event: Event, filters: dict[str, Any]) -> bool:
    text = normalized_search_text(event)
    url = event.url.casefold()
    source = event.source.casefold()
    category = event.category.casefold()

    if any(token.casefold() in url for token in filters.get("always_include_urls", [])):
        return True

    include = [word.casefold() for word in filters.get("include_keywords", [])]
    exclude = [word.casefold() for word in filters.get("exclude_keywords", [])]

    has_include = any(word in text for word in include)
    has_exclude = any(word in text for word in exclude)

    # Die spezielle Straßenfest-Seite ist bereits thematisch passend.
    trusted_street_source = (
        "straßen- und stadtfeste" in source
        or "straßenfest & veedel" in category
    )

    if trusted_street_source and not has_exclude:
        return True

    return has_include and not has_exclude

def within_window(event: Event, past_days: int, future_days: int) -> bool:
    try:
        event_date = dateparser.isoparse(event.start).date()
    except ValueError:
        return False
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    return today - timedelta(days=past_days) <= event_date <= today + timedelta(days=future_days)

def deduplicate(events: Iterable[Event]) -> list[Event]:
    chosen: dict[str, Event] = {}
    for event in events:
        if event.key not in chosen:
            chosen[event.key] = event
            continue
        current = chosen[event.key]
        score_new = len(event.description) + len(event.location) + bool(event.url) * 100
        score_old = len(current.description) + len(current.location) + bool(current.url) * 100
        if score_new > score_old:
            chosen[event.key] = event
    return sorted(chosen.values(), key=lambda item: item.start)

def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def fold(line: str) -> str:
    if len(line.encode("utf-8")) <= 73:
        return line
    pieces: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > 73:
            pieces.append(current)
            current = " " + char
        else:
            current = candidate
    pieces.append(current)
    return "\r\n".join(pieces)

def ics_datetime(value: str) -> tuple[str, str]:
    parsed = dateparser.isoparse(value)
    if not isinstance(parsed, datetime):
        return "VALUE=DATE", parsed.strftime("%Y%m%d")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    return "", parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def build_ics(events: list[Event], name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Koeln Events Filtered Calendar//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(name)}",
        "X-WR-TIMEZONE:Europe/Berlin",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]
    for event in events:
        start_param, start_value = ics_datetime(event.start)
        end_param, end_value = ics_datetime(event.end)
        uid = hashlib.sha256(event.key.encode()).hexdigest()[:32] + "@koeln-events"
        description = event.description
        if event.source:
            description += f"\nQuelle: {event.source}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART{';' + start_param if start_param else ''}:{start_value}",
            f"DTEND{';' + end_param if end_param else ''}:{end_value}",
            f"SUMMARY:{ics_escape(event.title)}",
            f"LOCATION:{ics_escape(event.location)}",
            f"DESCRIPTION:{ics_escape(description.strip())}",
            f"CATEGORIES:{ics_escape(event.category)}",
            f"URL:{event.url}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"

def render_index(events: list[Event], status: dict[str, Any]) -> str:
    items = "\n".join(
        f"<li><strong>{html.escape(e.title)}</strong> – {html.escape(e.start[:10])}"
        + (f" – {html.escape(e.location)}" if e.location else "") + "</li>"
        for e in events[:150]
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Köln – Straßenfeste, Bier- & Weinfeste</title>
<style>body{{font:16px system-ui;max-width:850px;margin:40px auto;padding:0 18px;line-height:1.5}}
a.button{{display:inline-block;padding:10px 14px;border:1px solid;border-radius:8px;text-decoration:none}}
small{{color:#555}}</style></head>
<body><h1>Köln – Straßenfeste, Bier- & Weinfeste</h1>
<p><a class="button" href="koeln-events.ics">ICS-Kalender abonnieren/herunterladen</a></p>
<p>{len(events)} ausgewählte Termine. Zuletzt erzeugt: {html.escape(status["generated_at"])}</p>
<p><small>Enthält nur passende öffentliche Feste und besondere Stadtveranstaltungen. Termine auf der Originalquelle prüfen.</small></p>
<ul>{items}</ul></body></html>"""

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    config = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    all_events = load_manual_events()
    failures: list[str] = []

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        try:
            scraped = scrape_source(source)
            LOG.info("%s: %d Event-Datensätze gelesen", source["name"], len(scraped))
            all_events.extend(scraped)
        except Exception as exc:
            failures.append(f'{source["name"]}: {exc}')
            LOG.error("%s", failures[-1])

    within_date = [
        event for event in all_events
        if within_window(event, past_days=7, future_days=int(config["look_ahead_days"]))
    ]
    events = [event for event in within_date if matches_filters(event, config.get("filters", {}))]
    events = deduplicate(events)

    LOG.info("Filter: %d von %d Terminen übernommen", len(events), len(within_date))

    if not events:
        LOG.warning("Der Filter hat keine Termine geliefert. Manuelle Termine werden als Reserve verwendet.")
        events = deduplicate(load_manual_events())

    if not events:
        LOG.error("Es sind weder automatische noch manuelle Termine vorhanden.")
        return 2

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "koeln-events.ics").write_text(
        build_ics(events, config["calendar_name"]), encoding="utf-8", newline=""
    )
    (docs / "events.json").write_text(
        json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "events_before_filter": len(within_date),
        "source_failures": failures,
    }
    (docs / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (docs / "index.html").write_text(render_index(events, status), encoding="utf-8")
    LOG.info("Fertig: %d eindeutige, gefilterte Termine", len(events))
    return 0

if __name__ == "__main__":
    sys.exit(main())
