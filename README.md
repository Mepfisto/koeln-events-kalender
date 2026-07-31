# Köln Events – automatisch aktualisierter ICS-Kalender

Das Projekt sammelt öffentliche Veranstaltungsdaten aus mehreren Kölner Quellen,
entfernt Dubletten und veröffentlicht täglich einen abonnierbaren ICS-Kalender
über GitHub Pages.

## Funktionen

- täglicher Lauf über GitHub Actions
- Event-Erkennung über strukturierte JSON-LD-Daten
- vorsichtiges Folgen passender Veranstaltungslinks
- Dublettenfilter
- manuelle Reserveeinträge
- Quellenfehler stoppen nicht den gesamten Kalender
- Statusdatei unter `docs/status.json`
- öffentliche Übersichtsseite unter GitHub Pages

## Wichtige Einschränkung

Webseiten können Aufbau und Nutzungsbedingungen ändern. Der Sammler verwendet
wenige tägliche Abrufe, einen erkennbaren User-Agent und bricht bei Fehlern
quellenweise ab. Neue oder geänderte Seitenstrukturen können Anpassungen in
`src/calendar_builder.py` oder `sources.json` erfordern.

## GitHub-Einrichtung

1. Neues **öffentliches** Repository `koeln-events-kalender` anlegen.
2. Den gesamten Inhalt dieses Projektordners hochladen.
3. Unter **Settings → Actions → General → Workflow permissions**:
   **Read and write permissions** aktivieren.
4. Unter **Settings → Pages → Build and deployment → Source**:
   **GitHub Actions** auswählen.
5. Unter **Actions → Kalender aktualisieren → Run workflow** den ersten Lauf starten.
6. Danach gegebenenfalls **GitHub Pages veröffentlichen** starten.

Die Webseite mit allen aufgeführten Kalenderadressen lautet:

`https://mepfisto.github.io/koeln-events-kalender/`

Die Kalenderadresse zum abonnieren lautet anschließend:

`https://mepfisto.github.io/koeln-events-kalender/koeln-events.ics`

## Quellen ändern

In `sources.json` kannst du Quellen aktivieren, deaktivieren oder ergänzen.
`link_patterns` begrenzt, welchen Links der Sammler folgt.

## Manuelle Termine

`data/manual_events.json` enthält Termine, die unabhängig von externen
Webseiten übernommen werden. Das Enddatum ganztägiger Ereignisse ist exklusiv:
Ein Fest am 10. und 11. August endet technisch am 12. August.

## Lokal testen

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.calendar_builder
```
