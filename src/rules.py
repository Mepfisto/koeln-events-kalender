from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RuleDecision:
    matched: bool
    include: bool
    reason: str


class EventLike(Protocol):
    title: str
    description: str
    category: str
    location: str
    url: str
    source: str


def normalize(value: str) -> str:
    return (value or "").casefold().strip()


def contains_any(text: str, values: list[str]) -> bool:
    return any(normalize(value) in text for value in values if value)


class Rule(Protocol):
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        ...


class ExplicitTitleBlockRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        title = normalize(event.title)
        if contains_any(title, config.get("blocked_titles", [])):
            return RuleDecision(
                matched=True,
                include=False,
                reason="Titel steht auf der Ausschlussliste: 'blocked_titles'",
            )
        return RuleDecision(False, False, "")


class HardExclusionRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        text = " ".join(
            normalize(value)
            for value in (
                event.title,
                event.description,
                event.category,
                event.url,
            )
        )
        if contains_any(text, config.get("hard_exclude_keywords", [])):
            return RuleDecision(
                matched=True,
                include=False,
                reason="Ausschlussbegriff erkannt: 'hard_exclude_keywords'",
            )
        return RuleDecision(False, False, "")


class ExplicitAllowRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        title = normalize(event.title)
        url = normalize(event.url)

        if contains_any(title, config.get("always_include_titles", [])):
            return RuleDecision(
                matched=True,
                include=True,
                reason="Titel steht auf der Positivliste: 'always_include_titles'",
            )

        if contains_any(url, config.get("always_include_urls", [])):
            return RuleDecision(
                matched=True,
                include=True,
                reason="URL steht auf der Positivliste: 'always_include_urls'",
            )

        return RuleDecision(False, False, "")


class TrustedSourceRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        source = normalize(event.source)
        trusted = {
            normalize(value)
            for value in config.get("trusted_sources", [])
        }
        if source in trusted:
            return RuleDecision(
                matched=True,
                include=True,
                reason="Freigegebene Straßenfest-Quelle: 'trusted_sources'",
            )
        return RuleDecision(False, False, "")


class FestivalTitleRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        title = normalize(event.title)
        if contains_any(
            title,
            config.get("festival_title_keywords", []),
        ):
            return RuleDecision(
                matched=True,
                include=True,
                reason="Passender Festbegriff im Titel: 'festival_title_keywords'",
            )
        return RuleDecision(False, False, "")


class DefaultRejectRule:
    def evaluate(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        return RuleDecision(
            matched=True,
            include=False,
            reason="Keine Positivregel erfüllt",
        )


class EventRuleEngine:
    def __init__(self) -> None:
        # Die Straßenfest-Quelle hat absolute Priorität.
        # Alle dort gefundenen Termine werden ungefiltert übernommen.
        self.rules: list[Rule] = [
            TrustedSourceRule(),
            ExplicitAllowRule(),
            ExplicitTitleBlockRule(),
            HardExclusionRule(),
            FestivalTitleRule(),
            DefaultRejectRule(),
        ]

    def decide(
        self,
        event: EventLike,
        config: dict[str, Any],
    ) -> RuleDecision:
        for rule in self.rules:
            decision = rule.evaluate(event, config)
            if decision.matched:
                return decision

        return RuleDecision(
            matched=True,
            include=False,
            reason="Keine Regelentscheidung",
        )
