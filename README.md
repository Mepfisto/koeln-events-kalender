# Köln Events – automatisch aktualisierter ICS-Kalender
[![Website](https://img.shields.io/badge/Website-online-brightgreen)](https://mepfisto.github.io/koeln-events-kalender/)
[![last commit](https://img.shields.io/github/last-commit/Mepfisto/koeln-events-kalender)](https://github.com/Mepfisto/koeln-events-kalender/commits/main/)

## Inhalt

- Projektbeschreibung
- Enthaltene Veranstaltungen
- Nicht enthalten
- Website
- Kalender abonnieren
- Aktualisierung
- Mitmachen
- Lizenz
- Geplant

---

## 🚀 Projektbeschreibung

Ein kostenloser Kalender mit ausgewählten Veranstaltungen in Köln. 
Das Projekt sammelt öffentliche Veranstaltungsdaten aus mehreren Kölner Quellen,
entfernt Dubletten und veröffentlicht täglich einen abonnierbaren ICS-Kalender
über GitHub Pages.

---

## 🎉 Enthaltene Veranstaltungen

Der Kalender enthält ausschließlich größere öffentliche Veranstaltungen mit Festcharakter.

Dazu gehören unter anderem:

- 🎉 Straßenfeste
- 🏘️ Stadtteil- und Veedelsfeste
- 🍺 Bierfeste und Bierbörsen
- 🍷 Weinfeste, Weinwochen und Winzerfeste
- 🌞 Sommer-, Herbst- und Hafenfeste
- 🎆 Kölner Lichter sowie vergleichbare Feuerwerks- und Lichterveranstaltungen
- 🎪 größere öffentliche Stadtfeste

---

## 🚫 Nicht enthalten

Bewusst herausgefiltert werden beispielsweise:

- 🎵 Konzerte
- 🎭 Theater und Musicals
- 🏃 Sportveranstaltungen
- 🏢 Messen und Kongresse
- 🎓 Führungen, Vorträge und Workshops
- 🎧 normale Club- und Partyveranstaltungen
- 🛍️ verkaufsoffene Sonntage
- 🎄 Weihnachtsmärkte
- 🛒 Flohmärkte

---

## 🌐 Website

➡️ **Kalender ansehen**

https://mepfisto.github.io/koeln-events-kalender/

---

## 📅 Kalender abonnieren

Den Kalender kannst du direkt in allen unterstützen Kalender abonnieren. Dazu folgenden Link kopieren und dem ausgewählten Mail-Client per Abo hinzufügen: 

**ICS-Adresse**

https://mepfisto.github.io/koeln-events-kalender/koeln-events.ics

---

### Unterstützte Kalender

| System                          | Unterstützt | Empfehlung                        |
| ------------------------------- | ----------- | --------------------------------- |
| 🍎 Apple Kalender (macOS)       | ✅          | Direkt abonnieren                 |
| 📱 iPhone/iPad                  | ✅          | Direkt abonnieren                 |
| 🌐 Google Kalender              | ✅          | Über die Weboberfläche hinzufügen |
| 🤖 Android                      | ✅          | ICSx⁵ oder Google Kalender        |
| 💼 Microsoft Outlook            | ✅          | Internetkalender                  |
| 🐦 Thunderbird                  | ✅          | iCalendar (ICS)                   |
| 🏠 Home Assistant               | ✅          | ICS-Integration                   |

---

### 🍎 Apple Kalender (macOS)

1. Kalender öffnen
2. Ablage
3. Neues Kalenderabonnement…
4. Die ICS-Adresse einfügen
5. Abonnieren
6. Aktualisierung auf **Täglich** oder **Stündlich** stellen.

---

### 📱 iPhone / iPad

1. Einstellungen
2. Apps
3. Kalender
4. Kalenderaccounts
5. Account hinzufügen
6. Andere
7. Abonnierten Kalender hinzufügen
8. Die ICS-Adresse einfügen
9. Weiter
10. Sichern

---

### 🌐 Google Kalender

1. https://calendar.google.com öffnen
2. Links neben **Weitere Kalender** auf **+**
3. Per URL
4. Die ICS-Adresse einfügen
5. Kalender hinzufügen

Hinweis:
Google synchronisiert abonnierte Kalender nicht sofort. Aktualisierungen können mehrere Stunden dauern.

---

### 💼 Microsoft Outlook (Web)

1. Outlook Kalender öffnen
2. Kalender hinzufügen
3. Aus dem Internet abonnieren
4. Die ICS-Adresse einfügen
5. Speichern

---

### 💼 Microsoft Outlook (Windows)

1. Datei
2. Kontoeinstellungen
3. Internetkalender
4. Neu
5. Die ICS-Adresse einfügen
6. OK

---

### 🐦 Thunderbird

1. Datei
2. Neu
3. Kalender
4. Im Netzwerk
5. Format **iCalendar (ICS)**
6. Die ICS-Adresse einfügen
7. Fertig

---

### 🏠 Home Assistant

```yaml
calendar:
  - platform: ics
    url: https://mepfisto.github.io/koeln-events-kalender/koeln-events.ics
```

---

## ⚙️ Aktualisierung

Der Kalender wird über GitHub Actions aktualisiert. Die Aktualisierung erfolgt immer täglich um 5:23 Winterzeit oder 6:23 zur Sommerzeit. Nach dem Abonnieren erscheinen neue Veranstaltungen automatisch, sobald dein Kalender synchronisiert.

---

## 🤝 Mitmachen

Fehlt eine Veranstaltung oder ist ein Termin falsch?

Erstelle gerne ein **Issue** oder sende einen **Pull Request**.

---

## 📜 Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

---

## Lokale Entwicklung

### Repository klonen

```bash
git clone https://github.com/Mepfisto/koeln-events-kalender.git
cd koeln-events-kalender
```

### Virtuelle Umgebung

1. Umgebung Erstellen:	            python3 -m venv .venv 
2. Aktivieren (Mac/Linux):          source .venv/bin/activate
2. Aktivieren (Windows):            .venv\Scripts\activate
3. Abhängigkeiten installieren:     pip install -r requirements.txt
4. Kalender erzeugen:				python -m src.calendar_builder
5. Umgebung verlassen:			    deactive
6. Umgebung löschen (optional):     rm -rf .venv

## 🚧 Geplant

- Suchfunktion
- Kategorienfilter
- Kartenansicht
- Import weiterer Veranstaltungen
