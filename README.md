# UrbanMobilityPrivacy

Forschungsbasis für die Dissertation zur Quantifizierung von Privacy und Utility
in urbanen Mobilitätsdaten und zur regional gesteuerten räumlich-zeitlichen Aggregation.

**Stand: 08.10.2026. Aktuelle Arbeitsphase: Bestand ordnen, Datensemantik klären und
Änderungen planen. Die erste ABS-Implementierung wurde auf Wunsch zurückgenommen.
Der aktive Quellcode entspricht wieder dem ursprünglichen Import.**

## 1. Wo anfangen?

| Dokument | Zweck |
|---|---|
| [README.md](README.md) | Projektüberblick, tatsächlicher Funktionsstand, Architektur, Datenfluss, Build und bekannte Grenzen |
| [TO-DO.md](TO-DO.md) | Priorisierte Aufgaben mit Befund, geplanter Änderung, offenen Entscheidungen und Abnahmekriterien |
| [Bestandsaufnahme](docs/STATE_AND_NEXT_STEPS.md) | Technische Befunde und nachvollziehbare Datenprüfung; ergänzt diese beiden zentralen Dokumente |
| [Alter Implementierungsplan](docs/reference/IMPLEMENTATION_PLAN.md) | Historische fachliche Referenz; keine automatisch auszuführende Arbeitsanweisung |

Für die nächste Sitzung zuerst den aktuellen Stand und Abschnitt 5 lesen, anschließend
in TO-DO.md die nächste konkrete Aufgabe auswählen. Bereits vorhandene Funktionen,
nachgewiesene Fehler und noch nicht beschlossene Architekturvorschläge sind getrennt gekennzeichnet.

## 2. Forschungsziel und nächster Meilenstein

Die Arbeit soll zwei zusammenhängende Fragen beantworten:

1. Wie verändern räumliche und zeitliche Aggregation die messbare Privacy und die
   Nutzbarkeit urbaner Mobilitätsdaten für eine konkret definierte Anwendung?
2. Kann ein System mit lokalen Constraints und adaptiven Raum-/Zeitfenstern unter
   vergleichbaren Bedingungen einen besseren Trade-off erzielen als feste Aggregation?

Dafür fehlen noch die verbindlichen Definitionen von Angreiferwissen, Angriffsziel,
Anwendungsabfrage und Bewertungsmetriken. Eine Mindestanzahl von Agenten pro Veröffentlichung
ist zunächst eine operative Freigaberegel. Sie ist für sich allein noch kein Nachweis
formaler k-Anonymität oder einer Verringerung des empirischen Angriffsrisikos.

**Nächster kleiner Meilenstein:** einen vorhandenen Messstrom verstehen, relevante
Korrekturen festlegen und danach feste räumliche/zeitliche Baselines nachvollziehbar
vergleichen. Der komplette adaptive Aggregator ist dafür noch keine Voraussetzung.
Die Simulation soll als schlanker Datengenerator erhalten bleiben.

Genannte Termine: Präsentationsabgabe am 18.10., Vortrag am 25.10., Paper Mitte November,
Dissertation Ende des Jahres. Für das Gespräch am möglichen Dienstag, 13.10., oder
Mittwoch, 14.10., ist ein klar belegbarer Zwischenstand sinnvoll. Das ist eine Arbeitsplanung,
keine Zusage eines bereits nachgewiesenen Privacy-Gewinns.

## 3. Herkunft und Repository-Struktur

Lokales Repo: `/Users/maxdemu/Developer/Coding/UrbanMobilityPrivacy`.
Import am 08.10.2026 aus `Coding`, Ausgangscommit
`d1e3dde748c6565ca4a44514d5e9e86016b67de3`.

```text
UrbanMobilityPrivacy/
├── README.md
├── TO-DO.md
├── .gitignore
├── simulator/                    # Import aus Aggregation_Manager
│   ├── CMakeLists.txt
│   ├── config.yaml
│   ├── include/
│   └── src/
├── renderers/                    # Getrennte Wiedergabe aus MongoDB
│   ├── abs/                      # ABS_Renderer_database_V3
│   ├── gbs/                      # GBS_Renderer_database_V3
│   ├── agbs/                     # AGBS_Renderer_database_V3
│   └── gt/                       # GT_Renderer_database_V3
└── docs/
    ├── STATE_AND_NEXT_STEPS.md
    └── reference/
        └── IMPLEMENTATION_PLAN.md
```

Die Originalprojekte wurden nicht verändert. Build-Artefakte und alte VS-Code-Konfigurationen
wurden nicht importiert. Die Komponenten bleiben zunächst getrennt baubar; noch keine
gemeinsame Bibliothek und kein CMake-Superprojekt. Ein Remote wurde nicht eingerichtet.

### Git-Verlauf und Rücknahme

| Commit | Bedeutung |
|---|---|
| `96fae5b` | Unveränderter Import von Simulator und vier Renderern |
| `ed4dc14` | Erste Bestandsaufnahme |
| `0ce473f` | Zwischenzeitlicher ABS-Fix samt Regressionstests; im aktiven Stand zurückgenommen |
| `db2bdbb` | Revert dieses Fixes; Historie bleibt nachvollziehbar erhalten |

Die damaligen Tests sind nach der Rücknahme nicht mehr Teil des aktiven Projekts.
Ihre früheren Ergebnisse sind kein Testnachweis für den aktuellen unveränderten Code.
Die Fehler bleiben dokumentiert und werden erst in einem nächsten abgestimmten Arbeitsschritt korrigiert.

## 4. Tatsächlicher Funktionsstand

| Bereich | Vorhanden | Noch offen / Einschränkung |
|---|---|---|
| Simulation | Agenten, Klassenattribute, Bewegung, Regionen, konfigurierbarer Zeitschritt | Kein zentraler Seed; Bewegungsnoise hängt teilweise an Wall-Clock-Zeit |
| Ground Truth | Agenten-ID, Position, Geschwindigkeit und Timestamp in MongoDB | Vollständigkeit über alle Runs und Randfälle noch nicht systematisch geprüft |
| ABS | Position, Typ, ID und positionsbasierte Geschwindigkeitsschätzung | Erstes Zeitintervall falsch; doppelte Writes; unbekannte Agenten ohne gültige Schätzung |
| GBS | Feste Zellen, Klassen-Counts und Gesamtzahl je Messzeitpunkt | Keine vollständige räumlich-zeitliche Auswertung oder Privacy-Entscheidung |
| AGBS | Quadtree, Positionszuordnung, Counts und Zell-IDs | Splits folgen Positionen/maximaler Tiefe; keine metric-/policygesteuerte Adaption |
| AggregationManager | Sensorlokal angelegte Klasse, Bucket-Struktur, DB-Testfunktion | Kein nutzbarer Aggregationsalgorithmus; flush leer; keine wirksame Einbindung |
| Regionale Regeln | YAML-/Region-Felder für Granularität und k-/l-Schwellen | Keine aktive Policy-Auswertung, Konfliktauflösung oder Policy-Trees |
| Zeitliche Historie | Kurzlebige Sensordaten-Container | Keine begrenzte rekonstruierbare Historie, keine variablen Aggregationsfenster |
| Renderer | Simulatoransicht und vier separate V3-MongoDB-Renderer | Snapshot-/Shutdown-Probleme; Veröffentlichungsansicht noch nicht definiert |
| Evaluation | Vorarbeiten außerhalb dieses Imports in Data_analysis | Metriksemantik, unabhängige Angreiferbewertung und fairer Baselinevergleich fehlen |
| Bewegung | Start/Ziel, geradlinige Wegpunkte, Noise und Kollisionsvermeidung | Keine realen Straßenrouten; TTC/Lookahead noch nicht validiert |
| Taxonomie | Gemeinsame Konfiguration von Typ, Verhalten, Darstellung und Verteilung | Zu stark gekoppelt; modularer Umbau noch nicht festgelegt |

Vorhandener Code bedeutet nicht automatisch, dass alle Randfälle geprüft sind.
Der Aggregator und die eigentliche Forschungsbewertung sind noch offen.

## 5. ABS: Zeitstempel, estimateVelocities und gespeicherte Geschwindigkeit

### 5.1 Sind GT und ABS zeitlich versetzt?

Im aktiven `Aggregation_Manager`-Import ist die Reihenfolge in `Simulation::run/update`:

```text
Zustand X(t), Timestamp t
    → GT und Agentensnapshot speichern
    → simulationTime intern erhöhen; Timestamp bleibt zunächst t
    → Sensoren beobachten X(t) mit Timestamp t
    → Timestamp auf t + dt setzen
    → Agenten zum nächsten Zustand bewegen
```

Für diesen Pfad beschreibt ein gemeinsamer Timestamp denselben Positionszustand.
Ein zweiter Frame zur Geschwindigkeitsschätzung erfordert keine Verschiebung des
Positions-Timestamps. Unterschiedliche Sensorfrequenzen erzeugen unterschiedliche
Messzeitpunktmengen; ABS muss nicht zu jedem GT-Tick einen Datensatz besitzen.

Die erste pauschale Einschätzung eines allgemeinen Timestamp-Versatzes wurde korrigiert.
Für den untersuchten Beispielagenten ist die Gleichheit auch durch Daten belegt.

### 5.2 Was prüft estimateVelocities wirklich?

In `simulator/src/Sensor.cpp` läuft `estimateVelocities()` über `previousPositions`
und prüft, ob dieselbe ID auch in `currentPositions` vorkommt. Es werden somit nur
Agenten verarbeitet, für die beide Positionsbeobachtungen vorhanden sind.
**Diese Grundidee ist richtig.**

Die Berechnung lautet dort jedoch:

```text
estimatedVelocity = (currentPosition - previousPosition) * frameRate
```

Damit wird ein Beobachtungsabstand von exakt `1 / frameRate` vorausgesetzt. Eine
bekannte alte Position sagt noch nicht, wann sie beobachtet wurde. Für einen korrekten
Geschwindigkeitswert muss auch der tatsächliche zeitliche Abstand stimmen.

### 5.3 Welche Berechnung landet tatsächlich in MongoDB?

Der aktive ABS-Pfad besitzt eine zweite Berechnung:

```text
AgentBasedSensor::update()
    → captureAgentData()
        → AgentData.estimatedVelocity direkt berechnen
        → AgentData in dataStorage verschieben
    → estimateVelocities(estimatedVelocities)
        → separate Map berechnen
    → previousPositions aktualisieren

AgentBasedSensor::postData()
    → dataStorage ausgeben
    → AgentData.estimatedVelocity als estimated_velocity speichern
```

Die Map aus `estimateVelocities()` wird in diesem BSON-Ausgabepfad nicht zurück in
`AgentData` übernommen. Deshalb verhindert die korrekte Schnittmengenprüfung dort
nicht automatisch falsche oder fehlende Werte in den gespeicherten ABS-Records.

In `captureAgentData()` wird zwar ebenfalls auf `previousPositions` geprüft,
aber der Datensatz wird anschließend auch dann angelegt, wenn die ID unbekannt war.
Das Feld bleibt in diesem Fall beim Standardwert von `sf::Vector2f`, also `(0, 0)`.
**Das ist keine gemessene Geschwindigkeit null, sondern eine fehlende Schätzung.**
Ein ruhender bekannter Agent und ein unbekannter neuer Agent sind damit im aktuellen
Schema nicht unterscheidbar. Die gewünschte Behandlung ist noch zu entscheiden.

### 5.4 Warum ist der erste bekannte Wert trotzdem falsch?

Die Simulation füllt `previousPositions` bereits aus den initialen GT-Positionen.
Der Sensor erhöht seinen Abtasttimer schon beim Aufruf für den Zustand `t = 0`.
Bei 50-ms-Simulationsticks und 10-Hz-ABS erfolgt die erste Ausgabe bei `t = 50 ms`.
Die alte Position stammt aber aus `t = 0`.

```text
Tatsächlicher Beobachtungsabstand: 50 ms
In der Formel angenommener Abstand: 1 / 10 Hz = 100 ms
Ergebnis: erste Geschwindigkeit wird halbiert
```

Danach liegen die Messungen in diesem Beispiel jeweils 100 ms auseinander, sodass
Positionsdifferenz × 10 für diese späteren Intervalle passt. Bei nichtganzzahligen
Frequenzverhältnissen oder veränderten Messabständen muss das erneut geprüft werden.

### 5.5 Warum werden ABS-Records doppelt geschrieben?

`update()` leert `agentData`, aber nicht den zuletzt gefüllten `dataStorage`-Batch.
`Simulation::update()` ruft `sensor->postData()` dagegen in jedem Simulationstick auf.
An einem Tick ohne neue ABS-Messung wird deshalb der vorherige Batch erneut eingefügt.

Es handelt sich um doppelte Veröffentlichungen, nicht um einen Timestamp-Shift.
Die Korrektur gehört zur Batch-Lebensdauer und Ausgabeplanung; sie benötigt keinen
zusätzlichen Aggregatorthread oder großen Simulatorumbau.

### 5.6 Tatsächlich geprüfter Datenbankfall

Lesend geprüft in `localhost:27017`, Datenbank `Simulation`:
Agent `C0B64FE1-740C-486C-A2D1-00E030269E71`.

| Prüfung | Ergebnis |
|---|---:|
| GT-Records in Agents | 200 |
| ABS-Records | 199 |
| Eindeutige ABS-Sensorzeitpunkte | 100 |
| ABS-Records ohne passenden GT-Timestamp | 0 |
| ABS-Positionsabweichungen bei gleicher ID und Zeit | 0 |
| Doppelte Schlüssel aus Sensor-ID, Agenten-ID und Timestamp | 99 |
| Zusätzliche Records durch diese Duplikate | 99 |
| Abweichende Inhalte innerhalb der Duplikate | 0 |

Erster Timestamp: `2025-04-09T09:30:00.050Z`. Über die vorhergehenden 50 ms ergeben sich
aus GT-Positionen `(5.105896, 1.291370) m/s`; ABS enthält `(2.552948, 0.645685) m/s`.
Alle 99 folgenden eindeutigen ABS-Werte stimmen mit der Positionsdifferenz über
100 ms überein. Das ist eine Prüfung dieses Agenten in diesem Datenbestand, keine
Validierung sämtlicher Agenten und Runs.

Momentane GT-Geschwindigkeit und ABS-Intervallgeschwindigkeit sind unterschiedliche
Größen: Ein Agent kann am Intervallende bereits stehen, obwohl er sich zuvor bewegt hat.
Der Geschwindigkeitsvergleich muss deshalb denselben Zeitabschnitt verwenden.

## 6. Architektur: Bestand und Plan getrennt halten

### Aktueller Datenfluss

```text
Simulationsthread
  ├── Agentenzustand → GT / MongoDB
  ├── ABS → Position / Geschwindigkeit / MongoDB
  ├── GBS → feste Zell-Counts / MongoDB
  ├── AGBS → Quadtree-Zell-Counts / MongoDB
  └── SharedBuffer → Renderer im Hauptthread

Separate V3-Renderer → lesen gespeicherte Daten aus MongoDB
```

### Diskussionsstand für die spätere Aggregation

Sensorlokale Aggregation ist der bevorzugte Ansatz: Der jeweilige Sensor koordiniert
Messung, Aggregation und Ausgabe. Der spätere AggregationManager sollte keine direkte
MongoDB-Abhängigkeit besitzen. Geometrie, temporale Historie, Policy-Auswertung und
Veröffentlichungszustand sind unterschiedliche Verantwortlichkeiten.

`AggregatedCell` ist ein sinnvoller möglicher Ausgabedatensatz. Vor seiner endgültigen
Definition muss `totalAgents` geklärt sein: momentane Belegung, Messbeiträge, eindeutige
Personen oder zeitlich gemittelte Belegung? Diese Größen sind nicht austauschbar.
Interne IDs können für Deduplizierung nötig sein; sie gehören nicht automatisch in Releases.

Die vorgeschlagenen Signaturen `update(now, tree)` und `update(now)` mit Baumreferenz
sind noch nicht entschieden. Ein Baum allein liefert keine Messhistorie. Obligat verfügbare
Abhängigkeiten können als Referenzen übergeben werden; ein optionaler Pointer ist nur
bei tatsächlich optionalem Zugriff sinnvoll. Eine neue Klassenhierarchie wird erst nach
Klärung der benötigten Zustände eingeführt.

Statische räumliche Hierarchie und dynamische Veröffentlichungsansicht sind ein brauchbarer
Entwurf. Ein voll materialisierter Max-Quadtree ist aber noch keine beschlossene Voraussetzung.
Der bestehende Baum besitzt vier Basiszellen und eigene ID-/Depth-Konventionen.

### SharedBuffer

`read()` entfernt einen Frame aus einer Queue. Zwei unabhängige Leser würden daher
verschiedene Frames konsumieren. Ein fester Zugriffscount von drei löst dieses Problem
nicht. Referenzzählung beschreibt Objektlebensdauer, nicht abgeschlossene Verarbeitung.

Zunächst kann Aggregation im bestehenden Simulationsthread bleiben. SharedBuffers werden
an tatsächlichen Threadgrenzen benötigt. Für Darstellung kann der jeweils neueste Snapshot
genügen; Auswertung und Persistenz benötigen ggf. jeden Batch. Diese Anforderungen werden
vor einer Transportänderung festgelegt. Kein neuer Thread als Standardlösung.

## 7. Technologie und Bezug zu UAM-Simulator-Modern

Dieser Simulator und die V3-Renderer verwenden C++17, SFML 3, yaml-cpp und den
MongoDB-C++-Treiber. `Aggregation_Manager` besitzt keinen direkten Metal-Backend.
Auch das Projekt `Coding/Metal-Simulator` verwendet trotz seines Namens OpenGL.

Das separat liegende Projekt `/Users/maxdemu/Developer/UAM-Simulator-Modern` verwendet
laut CMake tatsächlich Cocoa, Metal, MetalKit und QuartzCore sowie Objective-C++.
Seine README beschreibt C++-Simulationskern, Sensor-Snapshots und eine native 3D-Darstellung.
Es dient hier als Vorbild für nachvollziehbare Dokumentation: aktueller Meilenstein,
Build/Run, Datenexport, Einschränkungen und konkrete nächste Schritte.

Es wurde kein Metal-, Karten- oder Sensorgeometrie-Code daraus übernommen.
Ein Backendwechsel ist eine spätere Option, sofern ein konkreter Engpass oder
experimenteller Bedarf ihn rechtfertigt. Für die anstehenden Datenvergleiche ist ein
reproduzierbarer schlanker Messstrom zunächst wichtiger.

## 8. Build und Betrieb

### Abhängigkeiten

C++17-Compiler, CMake, SFML 3, yaml-cpp und mongocxx/bsoncxx.
Auf diesem Rechner wurde mit SFML 3.0.2 gebaut. Die bestehenden CMake-Dateien enthalten
Homebrew-Pfade; vollständige Portabilität ist noch nicht eingerichtet.

### Simulator bauen

Vom Repo-Verzeichnis:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j4
```

### Datenbank-Renderer bauen

```sh
cmake -S renderers/abs -B renderers/abs/build -DCMAKE_BUILD_TYPE=Release
cmake --build renderers/abs/build -j4
```

Für GBS, AGBS und GT `abs` durch `gbs`, `agbs` bzw. `gt` ersetzen.
Die Renderer heißen jeweils `Visualizer` und sind deshalb zunächst eigenständige Projekte.

### Konfiguration und Start

Die Programme laden `config.yaml` relativ zum Arbeitsverzeichnis. Im jeweiligen
Komponentenordner starten. Nach Prüfung der Datenbankkonfiguration gilt beispielsweise:

```sh
cd simulator
./build/Simulator
```

Die unveränderte Simulator-Konfiguration enthält `clear_database: true` und verweist auf
`Simulation`. Der Konstruktor löscht damit die konfigurierten GT-/Sensor-Collections.
Ein neuer Lauf darf nicht versehentlich die untersuchte Referenzreihe ersetzen.
Vor einem geplanten Lauf separate Experimentdatenbank und passende Einstellungen wählen.
Die Dokumentationsarbeit hat diese Konfiguration bewusst nicht geändert.

Bei einem Datenbank-Renderer lautet der Start im jeweiligen Ordner `./build/Visualizer`.
Auch dessen Konfiguration und tatsächlichen Initialisierungspfad vor Verwendung prüfen.
Schriftpfade sind noch macOS-spezifisch. `show_renderer: false` deaktiviert das Fenster,
aber derzeit nicht Datenbank-I/O oder Snapshot-Produktion.

### Ausgewählte Simulator-Steuerung

Aus dem vorhandenen Renderer-Code; hier nicht erneut interaktiv geprüft:

| Taste | Funktion |
|---|---|
| Space | Wiedergabe pausieren/fortsetzen |
| Links / Rechts | Wiedergabegeschwindigkeit ändern |
| R | Wiedergabegeschwindigkeit auf 1 zurücksetzen |
| A / B / C | Richtungspfeile / Pufferzonen / Kollisionsgrid anzeigen |
| S | Sensoransicht umschalten |
| T / W | Trajektorien / Wegpunkte umschalten |
| Esc / Q | Fenster schließen und Stop-Signal setzen |

Das Pausieren der Wiedergabe ist nicht automatisch eine Pause des Simulationsthreads.

## 9. Verifikation und bekannte Grenzen

Der unveränderte Import von Simulator und vier Renderern ließ sich als Release bauen.
101 Komponenten-Dateien wurden byteweise mit den Originalen verglichen.
Die lokale Datenbank wurde für Collection-Übersicht und den Beispielagenten nur gelesen.
Es wurde kein neuer Simulationslauf gestartet und kein vorhandener Record geändert.

Im aktiven Stand gibt es nach dem Revert keine neue CTest-Regressionstestsuite.
Weitere technische Befunde sind in der Bestandsaufnahme und TO-DO.md als offene Aufgaben
geführt: fehlender Seed, Wall-Clock-Noise, SharedBuffer-Shutdown, unbegrenzte Queues,
Kollisionsgrid-Grenzen/Pointer und Quadtree-Speicherfreigabe. Für diese Punkte liegen
vorwiegend Codebefunde vor; Laufzeitfolgen und Priorität sind noch zu prüfen.

## 10. Vorgehen ab jetzt

1. Bestand und Semantik dokumentieren; neue Befunde in TO-DO.md eintragen.
2. Einen kleinen konkreten Arbeitsschritt samt erwarteter Wirkung festlegen.
3. Nur die dafür notwendige Änderung implementieren.
4. Geeigneten reproduzierbaren Check durchführen und Ergebnis dokumentieren.
5. README-Status und TO-DO-Abnahme im selben Schritt aktualisieren.

Bestand, Befund, Vorschlag und implementiertes Verhalten dürfen nicht vermischt werden.
Karten, komplexes Path Planning, umfassender Taxonomie-Umbau und GPU-Optimierung bleiben
sichtbar im Backlog, blockieren aber nicht den ersten nachvollziehbaren Datenvergleich.
