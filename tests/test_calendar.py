from src.calendar_builder import Event, build_ics, deduplicate

def test_build_ics():
    event = Event("Testfest", "2027-01-01", "2027-01-02", location="Köln")
    result = build_ics([event], "Test")
    assert "BEGIN:VEVENT" in result
    assert "SUMMARY:Testfest" in result
    assert "DTSTART;VALUE=DATE:20270101" in result

def test_deduplicate():
    a = Event("Test Fest", "2027-01-01", "2027-01-02")
    b = Event("Test-Fest", "2027-01-01", "2027-01-02", description="Mehr Inhalt")
    assert len(deduplicate([a, b])) == 1
