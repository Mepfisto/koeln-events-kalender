from dataclasses import dataclass

from src.rules import EventRuleEngine


@dataclass
class FakeEvent:
    title: str
    source: str = ""
    description: str = ""
    category: str = ""
    location: str = ""
    url: str = ""


CONFIG = {
    "trusted_sources": [
        "koeln.de – Straßen- und Stadtfeste"
    ],
    "blocked_titles": [
        "Der Stoff der Nation",
        "HIER UND JETZT im Museum Ludwig",
        "Deafheaven",
        "Arch Enemy",
        "Rick Astley",
        "Corrosion Of Conformity",
        "Less Than Jake",
        "Block-Party",
    ],
    "hard_exclude_keywords": [
        "flohmarkt",
        "konzert",
        "museum",
        "ausstellung",
    ],
    "always_include_titles": ["Kölner Lichter"],
    "always_include_urls": ["koelner-lichter.de"],
    "festival_title_keywords": [
        "straßenfest",
        "bierbörse",
        "weinfest",
    ],
}


def include(event: FakeEvent) -> bool:
    return EventRuleEngine().decide(
        event,
        CONFIG,
    ).include


def test_trusted_street_source_is_included():
    assert include(
        FakeEvent(
            title="Deutz feiert!",
            source="koeln.de – Straßen- und Stadtfeste",
        )
    )



def test_every_event_from_trusted_source_is_included():
    assert include(
        FakeEvent(
            title="Hofflohmarkt in Ostheim",
            source="koeln.de – Straßen- und Stadtfeste",
        )
    )


def test_concert_from_trusted_source_is_included():
    assert include(
        FakeEvent(
            title="Beispielkonzert",
            source="koeln.de – Straßen- und Stadtfeste",
            description="Konzert",
        )
    )

def test_known_concert_is_excluded():
    assert not include(FakeEvent(title="Arch Enemy"))


def test_museum_event_is_excluded():
    assert not include(
        FakeEvent(
            title="HIER UND JETZT im Museum Ludwig",
            description="Ausstellung im Museum",
        )
    )


def test_koelner_lichter_is_included():
    assert include(FakeEvent(title="Kölner Lichter 2026"))


def test_wine_festival_is_included():
    assert include(FakeEvent(title="Weinfest am Rhein"))


def test_unknown_event_is_rejected():
    assert not include(FakeEvent(title="Faszination Köln"))
