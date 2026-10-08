# Bestandsaufnahme und nächste Schritte — 2026-10-08

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
verwendet ebenfalls OpenGL. In den geprüften Quellen wurde keine direkte Metal-,
MetalKit- oder Accelerate-Anbindung gefunden. Ein neuer Renderer ist für den ersten
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
- update leert agentData, nicht den zuletzt gefüllten dataStorage-Batch. Da Simulation
  postData bei jedem Tick aufruft, wird derselbe ABS-Batch an Nicht-Messticks erneut eingefügt.
  Im Beispiel: Messung bei 0.05 s, erneuter Write dieses Batches im Tick 0.10 s.
- Eine zweite Geschwindigkeitsberechnung im Sensor-Basistyp füllt eine Map, ist aber nicht
  die Quelle des BSON-Felds estimated_velocity.

Zum Audit-Zeitpunkt vorgeschlagen: erste Beobachtung intern speichern, erst mit zweiter Beobachtung für dieselbe
ID einen ABS-Record mit Geschwindigkeit ausgeben. Geschwindigkeit aus tatsächlichem
Delta-t berechnen; erster Messzeitpunkt muss explizit festgelegt sein. Messbatch einmalig
publizieren. Kein Timestamp künstlich verschieben. Noch keine Codeänderung vorgenommen.

Für die spätere Prüfung: ABS mit GT über ID+Timestamp verbinden, Positionen vergleichen,
fehlende Zuordnungen und doppelte Schlüssel zählen. Geschwindigkeitsvergleich muss die
mittlere GT-Bewegung über dasselbe Intervall verwenden; momentane GT-Geschwindigkeit
und Intervallgeschwindigkeit sind unterschiedliche Größen. Noch keine DB-Auswertung.

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

## Nächster kleiner Arbeitsabschnitt

- Kontrollierter Referenzlauf ohne DB-Schreibzugriff und ohne Renderabhängigkeit.
- Beobachtungszeit, Messfrequenz und einmalige ABS-Publikation korrigieren und prüfen.
- Gemeinsamen Seed, Simulationszeit für Noise, deterministische fachliche Agenten-IDs.
- Gespeicherten Messstrom für alle verglichenen Aggregationsvarianten wiederverwenden.
- Feste Raum-/Zeit-Baselines; Belegungsabfrage auf unverändertem Referenzraster und
  Referenzzeitplan gegen GT messen. Empty/Suppressed/Unavailable unterscheiden.
- Einfachen Membership-Angreifer mit definiertem Zusatzwissen und Prior-Baseline evaluieren.
- Erst danach adaptiven Manager, temporale Historie und regionale Policy-Vergleiche erweitern.

Ziel für Dienstag/Mittwoch: ein reproduzierbarer erster Vergleich mit transparenten
Grenzen. Keine Zusage eines bereits belegten Privacy-Gewinns oder des vollständigen Systems.

## Validierung des lokalen Imports

Simulator und ABS/GBS/AGBS/GT-Renderer jeweils separat mit CMake als Release gebaut:
alle fünf Builds erfolgreich. Build-Artefakte unter /private/tmp/diss-review/import-build.
101 übernommene Komponenten-Dateien byteweise gegen die Originale geprüft: identisch.
Keine Simulatorausführung und keine Datenbankabfrage oder -änderung.
Der neue Git-Verlauf beginnt mit dem unveränderten Import; kein Remote eingerichtet.

## ABS-Korrektur — 2026-10-08

Die Prüfung des Beispielagenten in der bestehenden DB bestätigte: 200 GT-Records,
199 ABS-Records für 100 verschiedene Sensorzeitpunkte, 99 identische doppelte Records.
Alle ABS-Positionen und -Zeitstempel passen zum GT. Die erste Geschwindigkeitsmessung
war exakt halbiert; die folgenden 99 passen zur mittleren Bewegung über 100 ms.

Im neuen Repo korrigiert:

- initializeObservations speichert Position und Timestamp der initialen GT-Beobachtung.
- Geschwindigkeit verwendet das tatsächliche positive Delta-t der Beobachtungen.
- Agenten ohne vorherige Beobachtung erhalten keinen Platzhalter-Record.
- Nicht-Messticks leeren den alten Batch. takeMeasurements konsumiert einen neuen Batch
  einmalig und wird von postData verwendet. Kein automatischer Retry nach DB-Fehlern;
  dies ist keine Garantie gegen externe Duplikate oder für verlustfreie Persistenz.
- GT-Zeitstempel, Sensorfrequenz und die Simulations-/Bewegungsreihenfolge bleiben erhalten.

Simulator-Release-Build erfolgreich; CTest AgentBasedSensorRegression mit fünf Szenarien
bestanden: erstes 50-ms-Intervall, einmaliger Konsum/stale Batch, abweichende Intervalle,
Neueintritt/Wiedereintritt und Nullzeitintervall. Tests benötigen weder MongoDB-Verbindung
noch Grafikfenster. Der Simulator wurde nicht gestartet, bestehende DB-Daten nicht geändert.
