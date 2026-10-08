# Technische Bestandsaufnahme — 2026-10-08

## Einordnung und aktueller Status

Diese Datei dokumentiert die Befunde zum unveränderten Import. Die zentralen aktuellen
Dokumente sind [README](../README.md) und [TO-DO](../TO-DO.md). Ausführung und Priorisierung
stehen in TO-DO.md; diese Bestandsaufnahme ist kein zweiter Implementierungsauftrag.

Der zwischenzeitliche ABS-Fix `0ce473f` einschließlich Tests wurde durch `db2bdbb`
zurückgenommen. Aktiver Quellcode und CMake entsprechen wieder dem Import `96fae5b`.
Die bekannten Fehler sind deshalb weiterhin offen. Historische Testresultate des Fixes
sind kein Nachweis für den aktuellen Stand. Weitere Implementierung ist derzeit nicht begonnen.

## Umfang

Quellcodeprüfung von Aggregation_Manager und SimulatorV3 sowie Grafik-Backend-Prüfung
von Metal-Simulator und UAM-Simulator. Die vier V3-Datenbank-Renderer sind unverändert
in das neue lokale Repository übernommen. Der alte IMPLEMENTATION_PLAN ist eine
Referenz, keine vom Nutzer erteilte Implementierungsanweisung.

## Arbeitsbasis

Aggregation_Manager ist die sinnvollere Basis: explizit zeitgestempelte Agenten- und
Sensorsnapshots und ein bereits sensorlokal angelegter Aggregator. Das ist noch kein
funktionsfähiger Aggregationsalgorithmus. AggregationManager::postDataTest schreibt
nur einen Timestamp, Bucket::flush ist leer und die Update-Pipeline ruft den Aggregator
nicht auf. Der Bucket-Konstruktor übernimmt cellId nicht in das gleichnamige Feld.

Die vorhandene Simulation ist als synthetischer Datengenerator brauchbar, aber noch
kein validiertes Modell urbaner Mobilität und noch kein reproduzierbares Experiment.
Es gibt Sensorvarianten, konfigurierbare Regionen und Klassen, Kollisionsgrid,
Visualisierung und MongoDB-Persistenz. Komplexere Trajektorien und Stadtgeometrie fehlen.

## Grafik und Apple-Frameworks

Aggregation_Manager und SimulatorV3 verwenden SFML Graphics. Metal-Simulator heißt
zwar so, baut aber einen OpenGL-2.1-Kontext und verwendet gl*-Aufrufe. UAM-Simulator
verwendet ebenfalls OpenGL. In diesen im Coding-Ordner geprüften Quellen wurde keine direkte Metal-,
MetalKit- oder Accelerate-Anbindung gefunden. Das später ebenfalls gelesene separate
Projekt `/Users/maxdemu/Developer/UAM-Simulator-Modern` verwendet dagegen Cocoa, Metal,
MetalKit und QuartzCore direkt; dies ist die gesuchte native Apple-Variante. README und
TO-DO dieses Projekts dienen als Dokumentationsvorbild, nicht als Implementierungsauftrag. Ein neuer Renderer ist für den ersten
Privacy/Utility-Vergleich nicht erforderlich; eine Beschleunigung ist noch nicht gemessen.

## Zeitstempel: präzisierter Befund

Eine erste mündliche Einschätzung eines GT-/Sensor-Versatzes war zu pauschal.
In Aggregation_Manager besteht folgende Reihenfolge:

1. Zustand X(t) und Timestamp t als Agentensnapshot und GT speichern.
2. simulationTime erhöhen; das Timestamp-Feld bleibt zunächst t.
3. Sensoren lesen X(t) mit Timestamp t.
4. Timestamp auf t+dt setzen und Agenten zu X(t+dt) bewegen.
5. Nächste Schleifeniteration speichert GT für t+dt.

GT und Sensorpositionen sind auf diesem Pfad zeitlich konsistent. ABS übernimmt die
Agenten-ID direkt; eine Zuordnung über (agent_id, timestamp) ist grundsätzlich möglich.
Sensorfrequenz und Erfassungsbereich bestimmen die Teilmenge. Unterschiedliche
Sensorfrequenzen müssen nicht identische Timestamp-Mengen erzeugen.

Auch SimulatorV3 speichert GT vor der Bewegung, verwendet dabei aber agent.timestamp
statt der bereits erhöhten simulationTime. ABS misst nach der Bewegung. Der zugehörige
GT-Zustand wird im nächsten Durchlauf gespeichert. Daraus folgt kein genereller
Timestamp-Shift; ein letzter Sensorzustand kann jedoch ohne nachfolgenden GT-Write bleiben.

### ABS-Geschwindigkeit und doppelte Releases

Im importierten Aggregation_Manager sind konkrete separate Probleme erkennbar:

- previousPositions wird bei Initialisierung aus X(0) vorbesetzt.
- timeSinceLastUpdate wird schon beim Sensoraufruf für X(0) um dt erhöht.
- Geschwindigkeit wird als Positionsdifferenz * frameRate berechnet, nicht über
  gespeicherte Beobachtungszeitpunkte.
- Bei dt=0.05 s und 10 Hz wird die erste Messung für t=0.05 s freigegeben, der Nenner
  entspricht aber 0.10 s. Bei konstanter Bewegung wird der erste Wert halbiert.
  Bei einer Messung direkt für t=0 ergibt sich eine Null-Differenz ohne vergangenes Intervall.
- Neu eintretende Agenten ohne vorherige Beobachtung werden trotzdem als Datensatz angelegt;
  es gibt keinen ausdrücklichen Status, der eine fehlende Geschwindigkeitsmessung kennzeichnet.
  sf::Vector2f initialisiert seine Komponenten in der lokalen SFML-3.0.2-Version mit null;
  deshalb wird für unbekannte Agenten ein Standardwert (0,0) statt einer gültigen Schätzung gespeichert.
- update leert agentData, nicht den zuletzt gefüllten dataStorage-Batch. Da Simulation
  postData bei jedem Tick aufruft, wird derselbe ABS-Batch an Nicht-Messticks erneut eingefügt.
  Im Beispiel: Messung bei 0.05 s, erneuter Write dieses Batches im Tick 0.10 s.
- Eine zweite Geschwindigkeitsberechnung im Sensor-Basistyp füllt eine Map, ist aber nicht
  die Quelle des BSON-Felds estimated_velocity.

Vorschlag: erste Beobachtung intern speichern, erst mit zweiter Beobachtung für dieselbe
ID einen ABS-Record mit Geschwindigkeit ausgeben. Geschwindigkeit aus tatsächlichem
Delta-t berechnen; erster Messzeitpunkt muss explizit festgelegt sein. Messbatch einmalig
publizieren. Kein Timestamp künstlich verschieben. Noch keine Codeänderung vorgenommen.

Für die spätere Prüfung: ABS mit GT über ID+Timestamp verbinden, Positionen vergleichen,
fehlende Zuordnungen und doppelte Schlüssel zählen. Geschwindigkeitsvergleich muss die
mittlere GT-Bewegung über dasselbe Intervall verwenden; momentane GT-Geschwindigkeit
und Intervallgeschwindigkeit sind unterschiedliche Größen. Die konkrete DB-Prüfung dieses Agenten ist unten dokumentiert; eine Gesamtprüfung aller Runs fehlt.

## Weitere Probleme vor größeren Experimenten

- Zufallszahlen werden an mehreren Stellen mit random_device initialisiert. Ein einzelner
  konfigurierbarer Seed fehlt; UUIDs und Iterationsreihenfolgen separat berücksichtigen.
- updateVelocity erhält simulationRealTime statt simulationTime. CPU-/DB-/Renderlaufzeit
  beeinflusst somit den Bewegungsnoise und die fachlichen Ergebnisse.
- SharedBuffer::read wartet nur auf nichtleere Queue. end setzt finished und benachrichtigt,
  aber das Wait-Prädikat berücksichtigt finished nicht; ein wartender Leser kann hängenbleiben.
- Queues sind unbegrenzt. Headless deaktiviert nur Renderer, nicht Snapshot-Produktion.
- CollisionGrid::width und height werden im Konstruktor nicht initialisiert, aber zur
  Prüfung der Nachbarzellen gelesen. Nachbarpaare werden beidseitig geprüft.
- Agentenpointer werden während einer Schleife gespeichert, die auch vector::erase
  verwendet; spätere Löschungen können vorher gespeicherte Pointer invalidieren.
- Quadtree::reset setzt Child-Pointer ohne delete auf nullptr; die getrennten Knoten werden
  damit nicht mehr vom Baumdestruktor erreicht.
- Sensoren mit niedrigerer Frequenz setzen ihren Timer auf null statt Restzeit zu erhalten.
  Nichtganzzahlige Frequenzverhältnisse können die tatsächliche Abtastrate verändern.

Diese Befunde stammen aus Codeprüfung, nicht aus Profiling oder Laufzeitvalidierung.

## Aggregator-Schnittstelle

Ein AggregatedCell als Veröffentlichungsdatensatz ist sinnvoll. Vorher die Count-Semantik
festlegen: Messbeiträge, eindeutige Personen oder zeitlich gemittelte Belegung. Ein einziges
Feld totalAgents kann diese drei Größen nicht austauschbar repräsentieren.

Sensorlokaler Manager; keine MongoDB-Abhängigkeit. Konstruktor erhält langlebige,
obligatorische Abhängigkeiten als Referenz, beispielsweise const SpatialHierarchy&,
TemporalStore& und PolicySet. Ein nullable Quadtree* bringt ohne optionale Baumzuordnung
keinen Vorteil. ingest(MeasurementBatch) und advance(SimTime) trennen Aufnahme von Planung.
Ein update(now, tree) ist als kleine Übergangsschnittstelle ebenfalls möglich, braucht
aber zusätzlich die Messhistorie; Geometrie allein reicht für Zeitaggregation nicht.

Zeitwerte als Simulations-Ticks oder integer chrono-Dauer, nicht float. Halb offene Fenster
[start,end) festlegen. Output-Batches besitzen sensor/policy ID, Release-ID und Releasezeit.
Agenten-IDs bleiben intern. Metriken/Unterdrückungsentscheidungen separat als Evaluationsdaten
führen. getOutput als const Referenz ist nur für direkten synchronen Zugriff geeignet;
Threadübergabe braucht unveränderliche Snapshots. takeOutput/drain verhindert wiederholtes
Publizieren desselben Batches.

## SharedBuffer

Keinen festen Zugriffscount 3 einsetzen. Schreiben erzeugt Daten; der Zähler muss weder
Schreibvorgänge mitzählen noch sagt eine Pointer-Referenzzahl, dass ein Leser fertig ist.
Im Bestand entfernt read einen Frame aus einer Queue: zwei Leser bekämen verschiedene Frames.

Zunächst Aggregation im Simulationsthread; kein zweiter interner Leser des SharedBuffers.
Für Renderer ein geschützter latest-snapshot-Kanal mit shared_ptr<const Frame>; Überspringen
von Frames zulässig. Vollständige Mess-/Release-Streams für Aggregator, Persistenz und
Evaluation benötigen begrenzte Queues mit expliziter Überlastregel. Mehrere verlustfreie
Leser benötigen eigene Queues oder individuelle Lesecursor. Snapshot-Lebensdauer und
Verarbeitungsvollständigkeit getrennt behandeln. Bestehende shared_ptr-Snapshots sind ein
brauchbarer Ansatz, aber Transport, Shutdown und Synchronisierung benötigen Überarbeitung.

## Bewertung des alten Plans

Weiterhin gut: sensorlokale Aggregation, Trennung von Topologie und Historie,
regionale Constraints, kein MongoDB im Manager, begrenzte Historie, klare Messsemantik,
separate Veröffentlichungsansicht und Referenzdaten.

Anpassungen:

1. Reproduzierbarkeit, Experiment-Runner, Ausgabe ohne MongoDB und Baselines zuerst.
2. Messbare Anwendungs-Utility und unabhängigen empirischen Angreifer früh definieren;
   Constraint-Compliance und Zellauflösung allein beantworten die Forschungsfrage nicht.
3. k-Mindestanzahl bleibt Freigaberegel; daraus folgt keine formale Anonymitätsgarantie.
4. Statische Hierarchie bedeutet nicht zwingend voll materialisierter Baum. Implizite
   Morton-Hierarchie/sparse Messspeicher prüfen. Der vorhandene Baum beginnt mit vier
   Basiszellen bei depth=1; Knotenformeln und IDs müssen diese Konvention berücksichtigen.
5. Spatial/Temporal First zunächst mit einer globalen Policy; regionale Konflikte danach.
6. Retrospektive Rekonstruktion betrifft interne Rohmessungen. Ein DB-Delete widerruft
   keine bereits extern zugängliche Veröffentlichung. Überlappung und Differenzangriffe
   müssen anhand des gesamten Release-Streams geprüft werden.
7. Einbehaltene Messbeiträge sind Coverage/Retention, nicht allein Data Fidelity.
8. Karten, ORCA, Sensorrauschen und Taxonomie-Umbau nur bei konkretem experimentellem Bedarf.
9. Die im Plan behauptete Kerninnovation bleibt Forschungshypothese, kein Nachweis.

## Nächster Arbeitsschritt

Die priorisierte Aufgabenliste steht ausschließlich in [TO-DO.md](../TO-DO.md).
D01/D02 klären Beobachtungs-/Ausgabesemantik; F01/F02 beschreiben die minimalen ABS-Fixes.
Diese Schritte sind offen. Keine weitere Implementierung im Rahmen der Dokumentationsarbeit.

## Validierung des lokalen Imports

Simulator und ABS/GBS/AGBS/GT-Renderer jeweils separat mit CMake als Release gebaut:
alle fünf Builds erfolgreich. Build-Artefakte unter /private/tmp/diss-review/import-build.
101 übernommene Komponenten-Dateien byteweise gegen die Originale geprüft: identisch.
Zur Importvalidierung keine Simulatorausführung oder Datenbankzugriffe. Später erfolgten
ausschließlich lesende DB-Abfragen für die unten dokumentierte Prüfung; keine Datenänderung.
Der neue Git-Verlauf beginnt mit dem unveränderten Import; kein Remote eingerichtet.

## Nachweis aus der bestehenden MongoDB — 2026-10-08

Datenbank localhost:27017/Simulation, Agent
`C0B64FE1-740C-486C-A2D1-00E030269E71`, Sensor
`40F5B238-1457-499C-A2CF-499BD5BF8AF6`.
Abfragen waren ausschließlich lesend; keine Löschung, Indexänderung oder neue Simulation.

| Prüfung | Ergebnis |
|---|---:|
| GT-Records / eindeutige GT-Timestamps | 200 / 200 |
| ABS-Records / eindeutige Sensor-Timestamps | 199 / 100 |
| Fehlende GT-Zuordnungen über Agenten-ID + Timestamp | 0 |
| Positionsabweichungen gegenüber zugeordnetem GT | 0 |
| Typabweichungen | 0 |
| Doppelte ABS-Schlüssel / zusätzliche Records | 99 / 99 |
| Abweichender Inhalt innerhalb der Duplikate | 0 |
| Folgeintervalle zwischen eindeutigen ABS-Messungen | 99 × 100 ms |

GT-Zeitbereich: 2025-04-09T09:30:00.000Z bis 09:30:09.950Z.
ABS-Zeitbereich: 09:30:00.050Z bis 09:30:09.950Z.

Die erste Positionsdifferenz über 50 ms ergibt (5.1058959961, 1.2913703918) m/s;
gespeichert wurden (2.5529479980, 0.6456851959) m/s. Der erste Wert ist exakt halbiert.
Die folgenden 99 eindeutigen Werte stimmen mit den Positionsdifferenzen über 100 ms
überein. GT enthält 183 Intervalle mit Positionsänderung; die Prüfung war somit nicht
auf einen ausschließlich unbewegten Agenten beschränkt. Die Anfangsbeispiele enthalten
allerdings auch Stillstand.

Dieser Nachweis bestätigt Timestamp-/Positionsgleichheit und die beiden ABS-Probleme
für diesen Datenbestand. Er beweist keine universelle Richtigkeit aller Sensoren/Runs.

## Warum estimateVelocities den Ausgabefehler nicht verhindert

Sensor::estimateVelocities läuft über previousPositions und prüft currentPositions;
Agenten ohne alte Position sind dort korrekt ausgeschlossen. AgentBasedSensor::update
ruft diese Methode aber erst nach captureAgentData auf. captureAgentData berechnet
AgentData.estimatedVelocity separat und verschiebt die Records bereits in dataStorage.
postData schreibt diese Records, nicht die separate estimatedVelocities-Map.

Daher sind drei Fragen getrennt zu beantworten:

1. Existieren zwei Positionsbeobachtungen derselben ID? Für unbekannte Agenten zunächst nein.
2. Welches tatsächliche Zeitintervall liegt zwischen ihnen? Beim ersten bekannten Wert 50 ms.
3. Welche Berechnung wird veröffentlicht? Aktuell diejenige in captureAgentData.

Die geplante Konsolidierung und Datenregel stehen als offene Aufgaben D01/D02 und F01/F02
in TO-DO.md. Der Simulationsapparat soll dafür schlank bleiben.
