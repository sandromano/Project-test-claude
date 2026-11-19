# E-Scooter Finder

Eine kleine Streamlit-App, die verfügbare E-Scooter aus der Schweizer
Shared-Mobility-Datenplattform auf einer Karte zeigt und zeitgestempelte
Snapshots für spätere Analysen speichert.

## Datenlage und Quelle

Die App verwendet die REST-API des Bundesamts für Energie (BFE),
insbesondere den Endpunkt `/v1/sharedmobility/identify`. Er unterstützt die
Suche um einen Mittelpunkt mit Radius sowie Filter für Fahrzeugtyp,
Verfügbarkeit und Abholart. Die API liefert höchstens 50 Einträge pro Anfrage;
der Client fragt weitere Seiten ab.

Die Karte und der Collector berücksichtigen nur `free_floating`-Scooter:
Diese Datensätze beschreiben einzelne Fahrzeuge. Bei station-basierten
Angeboten liefert die API Parkzonen statt einzelner Scooter-Positionen; die
angezeigte Verfügbarkeit kann zudem Fahrzeuge verschiedener Typen zusammen-
fassen. Solche Einträge werden deshalb nicht als einzelne Scooter gezählt.
Der Akkustand wird in der BFE-Antwort derzeit nicht mitgeliefert und bleibt
leer.

Bei einem Live-Test am 19. November 2026 lieferte die Suche im Umkreis von
5 km um St. Gallen keine frei fahrenden Scooter. Dott-St.-Gallen-Einträge
waren station-basierte Parkzonen; die geprüften Zonen meldeten 0 verfügbare
Fahrzeuge. Ob und wie viele Scooter angezeigt werden, kann sich ändern.
Für einen Vergleich kann der Ort in `config.toml` etwa auf Zürich umgestellt
werden.

**Quellenangabe:** Schweizerisches Bundesamt für Energie (BFE),
«Standorte und Verfügbarkeit von Shared-Mobility-Angeboten»,
[Datensatz auf opendata.swiss](https://opendata.swiss/en/dataset/standorte-und-verfugbarkeit-von-shared-mobility-angeboten),
[API-Dokumentation](https://api.sharedmobility.ch),
[GBFS-Dokumentation](https://github.com/SFOE/sharedmobility).

## Installation

Voraussetzung ist Python 3.11 oder neuer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## App starten

```bash
streamlit run app.py
```

In der Seitenleiste lassen sich Anbieter auswählen und die Daten aktualisieren.
Die API-Antwort wird 60 Sekunden zwischengespeichert; «Aktualisieren» leert
diesen Cache. Die Seite «Prognose» ist ein Platzhalter und enthält noch kein ML.

## Datensammler starten

```bash
python collector.py
```

Der Prozess fragt standardmässig alle 15 Minuten ab und schreibt jeden
erfolgreichen Snapshot in `data/scooters.sqlite3`. Auch ein erfolgreicher
Snapshot mit 0 Scootern wird gespeichert. Gleiche Zeitpunkte und Scooter-IDs
werden durch eindeutige Datenbankschlüssel nicht doppelt angelegt. Fehler
werden protokolliert; der Sammler versucht es beim nächsten Intervall erneut.
Mit `Ctrl+C` wird er beendet.

### Dauerbetrieb

Für eine lokale Installation eignet sich ein `systemd`-Dienst, der den Prozess
beim Systemstart startet und nach einem Absturz neu startet. Alternativ kann
der Befehl in `tmux` laufen. Eine SQLite-Datei in GitHub Actions ist für
dauerhafte Datensammlung ungeeignet: Runner sind kurzlebig und teilen ihre
Dateien nicht zuverlässig zwischen Ausführungen. Actions kann periodisch
laufen, wenn die Datenbank als Artefakt gesichert oder in einen persistenten
Speicher geschrieben wird; das ist für dieses Fundament bewusst nicht
eingerichtet.

## Ort und Intervall anpassen

`config.toml` enthält Stadtname, Mittelpunkt (Breiten- und Längengrad),
Suchradius, Intervall und Datenbankpfad. Für Zürich können zum Beispiel
`city`, `latitude` und `longitude` im Abschnitt `[city]` geändert werden:
`name = "Zürich"`, `latitude = 47.3769` und `longitude = 8.5417`.
Die API-Suche nutzt den konfigurierten Mittelpunkt und Radius.

### Beispiel für `systemd`

Lege unter `/etc/systemd/system/scooter-collector.service` einen Dienst an
und ersetze `/pfad/zum/projekt` durch den absoluten Projektpfad:

```ini
[Unit]
Description=E-Scooter Finder Datensammler
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/pfad/zum/projekt
ExecStart=/pfad/zum/projekt/.venv/bin/python collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Danach einmalig aktivieren und starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scooter-collector
sudo systemctl status scooter-collector
```

Logs lassen sich mit `sudo journalctl -u scooter-collector -f` verfolgen.
Der Dienst läuft unter dem in der Service-Datei konfigurierten Benutzer und
benötigt Schreibrechte auf den Projektordner bzw. die SQLite-Datei.

## Projektstruktur

```text
.
├── app.py
├── collector.py
├── config.toml
├── requirements.txt
├── src/
│   ├── api_client.py
│   ├── database.py
│   └── settings.py
├── ml/
│   ├── __init__.py
│   └── prediction.py
└── tests/
    ├── test_api_client.py
    └── test_database.py
```

Die lokale Datenbank wird beim ersten Speichern automatisch erstellt und von
Git ignoriert.

## Tests

```bash
pytest
```
