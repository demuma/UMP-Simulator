# TO-DO — UrbanMobilityPrivacy

**Stand: 08.10.2026. Arbeitsmodus: Dokumentation und Planung vor weiterer Implementierung.**

Dieses Dokument ist die zentrale Aufgabenliste. README.md erklärt den aktuellen Stand;
hier stehen die ausstehenden Änderungen. Der alte IMPLEMENTATION_PLAN bleibt Referenz.
Eine dort formulierte Aufgabe wird nicht allein durch ihre Aufnahme zur sofortigen Implementierung.

## 1. Status und Prioritäten

- `[x]` erledigt und mit konkretem Nachweis abgeschlossen.
- `[ ]` offen; noch nicht implementiert oder fachlich noch zu entscheiden.
- **P0:** für korrekte Daten oder den nächsten kleinen Vergleich nötig.
- **P1:** für adaptive Aggregation, belastbare Evaluation oder Dissertation nötig.
- **P2:** Erweiterung; beginnt bei nachgewiesenem Bedarf.

Bei jeder Implementierung festhalten: betroffene Dateien, fachliche Wirkung,
Verifikationsverfahren, Ergebnis und verbliebene Grenzen. Keine Aufgabe nur deshalb
abhaken, weil eine Klasse oder Konfigurationsoption existiert.

## 2. Bereits erledigt: Ordnung und Bestandsaufnahme

- [x] Eigenes lokales Repo UrbanMobilityPrivacy eingerichtet; kein Remote.
- [x] Aggregation_Manager als Simulatorbasis und vier getrennte V3-Renderer importiert.
- [x] Import-Commit als Ausgangsbasis erhalten: `96fae5b`.
- [x] Simulator und vier Renderer im unveränderten Import erfolgreich gebaut.
- [x] 101 Komponenten-Dateien byteweise gegen die Originalprojekte geprüft.
- [x] Alten Implementierungsplan als historische Referenz unter docs/reference abgelegt.
- [x] Aktuelle Klassen-/Datenflussbefunde und zentrale Risiken dokumentiert.
- [x] Lokale MongoDB-Verbindung und Collections lesend geprüft.
- [x] Beispielagent auf GT-/ABS-Zuordnung, Duplikate und Geschwindigkeit geprüft.
- [x] Zwischenzeitlichen ABS-Fix einschließlich Testtarget zurückgenommen: `db2bdbb`.
- [x] README und TO-DO als zentrale Projektübersicht angelegt/überarbeitet.
- [x] UAM-Simulator-Modern als Dokumentationsvorbild gelesen; Metal-Zuordnung präzisiert.

**Nicht erledigt:** ABS-Fix im aktiven Code, umfassende Datenvalidierung,
reproduzierbarer Experiment-Runner, echte Adaption, Metrikdefinition und Privacy-Nachweis.
Die zurückgenommenen Änderungen sind als Historie vorhanden, nicht als aktive Funktion.

## 3. Nächster kleiner Arbeitsabschnitt

Noch keine vollständige Aggregator-Neuimplementierung starten. Empfohlene Reihenfolge:

1. **D01/D02:** Beobachtungs- und Ausgabesemantik für ABS festlegen.
2. **F01/F02:** Zwei belegte ABS-Fehler minimal korrigieren.
3. **V01:** IDs, Zeitstempel, Positionen, Geschwindigkeit und Duplikate kontrolliert prüfen.
4. **R01/R02:** Referenzmessstrom unabhängig von Zufallslauf und Verarbeitungslaufzeit sichern.
5. **E01/E02:** Eine Anwendungsabfrage und ein Angreiferszenario festlegen.
6. **B01:** Feste räumliche/zeitliche Aggregationen auf identischem Messstrom vergleichen.

Ein kleiner, nachvollziehbarer Vergleich ist das Ziel; mehr Infrastruktur wird nur gebaut,
wenn eine dieser Aufgaben sie tatsächlich braucht. Folgende Reihenfolge ist ein Vorschlag,
keine Zusage, alle Punkte bis Dienstag/Mittwoch fertigzustellen.

## 4. Daten- und Beobachtungssemantik

### D01 — Geschwindigkeit und fehlende Beobachtungen festlegen — P0

- [ ] Zwischen momentaner GT-Geschwindigkeit und mittlerer ABS-Geschwindigkeit unterscheiden.
- [ ] Verhalten bei neuem Agenten ohne previousPositions festlegen.
- [ ] Verhalten bei Austritt, Wiedereintritt und Beobachtungslücken festlegen.
- [ ] Initiale GT-Position als erste interne Beobachtung zeitlich eindeutig beschreiben.

**Befund:** estimateVelocities prüft die Schnittmenge aus previousPositions und
currentPositions. Das ist richtig. Die MongoDB-Ausgabe nutzt aber den separat in
captureAgentData erzeugten AgentData-Wert. Unbekannte Agenten werden aktuell trotzdem
als Record gespeichert und erhalten den Standardvektor `(0,0)`, ohne Gültigkeitskennzeichen.

**Schlanker Vorschlag:** erste Beobachtung intern merken; vollständigen ABS-Record erst
nach einer zweiten zeitlich passenden Beobachtung ausgeben. Alternativ positionsbasierte
Records mit explizit fehlender Geschwindigkeit zulassen. Die Alternative ist noch nicht
entschieden; ein null/valid-Feld darf nicht stillschweigend zur Vorgabe werden.

**Abnahme:** Ein neuer, ein bewegter bekannter und ein ruhender bekannter Agent lassen
sich fachlich unterscheiden. Die gewählte Regel ist in README und Datenbeschreibung erklärt.

### D02 — Zeit- und Messsemantik festlegen — P0

- [ ] Timestamp als Zeitpunkt des Positionszustands festhalten.
- [ ] Zeitpunkt einer Geschwindigkeitsmessung und ihr zurückliegendes Intervall beschreiben.
- [ ] Simulationszeit, Datenzeit, Veröffentlichungszeit und Wall-Clock-Verarbeitung trennen.
- [ ] Verhalten bei nicht passenden Sensorfrequenzen/Simulationsticks festlegen.
- [ ] Darstellung von absolutem Datum/UTC prüfen; generateISOTimestamp verwendet mktime.

**Befund:** Kein allgemeiner GT-/ABS-Timestamp-Shift im Aggregation_Manager-Import.
Die Sensoren lesen denselben Zustand mit demselben Timestamp wie GT. Intern wird
simulationTime früher erhöht als das Timestamp-Feld; diese Reihenfolge muss verständlich bleiben.

**Abnahme:** Eine kurze Tabelle erklärt einen vollständigen Tick und zwei Sensorbeobachtungen.
Keine Korrektur darf nur zur optischen Synchronisierung Timestamps künstlich verschieben.

### D03 — Aggregat-Counts und Fenster definieren — P0 vor Zeitaggregation

- [ ] Messbeiträge, eindeutige Personen, momentane Belegung und mittlere Belegung unterscheiden.
- [ ] Klassen-Counts und totalAgents/totalCount eindeutig benennen.
- [ ] Fenstergrenzen definieren, bevorzugt halb offen `[start,end)`.
- [ ] Empty, Suppressed und Unavailable auseinanderhalten.
- [ ] Interne IDs und veröffentlichtes Datenmodell trennen.

**Abnahme:** Mehrfach beobachtete Person zählt beim Distinct-Count einmal, beim
Messbeitrags-Count mehrfach. Einfache Beispieldaten demonstrieren die festgelegte Semantik.

## 5. Konkrete ABS-Korrekturen: gefunden, derzeit offen

### F01 — Tatsächlichen Beobachtungsabstand für Geschwindigkeit verwenden — P0

- [ ] Frühere Position und zugehörigen Beobachtungszeitpunkt gemeinsam vorhalten.
- [ ] Geschwindigkeit aus `DeltaPosition / DeltaTime` berechnen.
- [ ] Zero-/negative-DeltaTime behandeln.
- [ ] Doppelberechnung über captureAgentData und estimateVelocities konsolidieren.
- [ ] Gewünschte Regel für unbekannte Agenten aus D01 umsetzen.

**Betroffene Stellen:**
`simulator/src/AgentBasedSensor.cpp`: update, captureAgentData, ggf. postData;
`simulator/src/Sensor.cpp`: estimateVelocities;
`simulator/src/Simulation.cpp`: initializeSensors;
passende Header nur soweit nötig.

**Belegter Fehler:** Initialposition bei t=0 bekannt; erste ABS-Messung im Beispiel
bei t=50 ms. Positionsdifferenz × frameRate nimmt bei 10 Hz jedoch 100 ms an.
Das halbiert die erste Geschwindigkeit. Eine bekannte ID löst diesen Zeitfehler nicht.

**Minimaler Änderungsumfang:** Zwei Beobachtungen mit Zeitinformation sauber zuordnen.
Keine neue Transportarchitektur, kein extra Thread, kein allgemeines Trackingframework.
Eine gemeinsame vorherige Samplezeit genügt ggf. für synchron beobachtete Agenten;
agentenspezifische Zeitpunkte nur verwenden, wenn Eintritts-/Ausfallsemantik sie benötigt.
Die konkrete Datenstruktur wird nach D01/D02 gewählt.

**Abnahme:** Bekannte konstante Bewegung liefert beim ersten 50-ms-Intervall und späteren
100-ms-Intervallen dieselbe korrekte Geschwindigkeit. Abweichende Intervalle bleiben korrekt.
Position, agent_id und Timestamp passen weiterhin zum GT. Unbekannte Agenten erfüllen D01.

**Status:** Frühere Lösung in `0ce473f` zurückgenommen. Sie ist ein überprüfbarer Entwurf,
aber weder verbindliche Zielarchitektur noch im aktuellen Code aktiv.

### F02 — ABS-Messbatch nur einmal ausgeben — P0

- [ ] Ausgabebatch von Arbeitscontainer unterscheiden.
- [ ] Nicht-Messticks dürfen keinen alten Batch erneut ausgeben.
- [ ] Nach erfolgreicher Ausgabe Batch eindeutig abschließen/verbrauchbar machen.
- [ ] Verhalten bei DB-Fehler und partieller insert_many-Ausführung dokumentieren.

**Befund:** update leert agentData; postData liest den weiter bestehenden dataStorage-Batch.
postData wird jeden Simulationstick aufgerufen. Daraus entstehen wiederholte Inserts.

**Beleg:** Beispielagent hat 199 ABS-Records für 100 Zeitpunkte, davon 99 zusätzliche
identische Records. GT-Positionen und Timestamps sind dennoch korrekt.

**Minimaler Änderungsumfang:** eindeutige Batch-Lebensdauer oder Kennzeichen für neue Messung.
Noch kein generisches ISensorOutput nötig. Ein Unique-Index allein ersetzt die Ursache nicht.
Keine Bereinigung der bestehenden Datenbank als Teil der Codekorrektur.

**Abnahme:** Auf eine Messung folgt genau eine Ausgabe; wiederholter postData-Aufruf
und ein Nicht-Messtick erzeugen keine Wiederholung. Fehlerstrategie ist benannt.
Nicht pauschal eine Exactly-once-Garantie für Netzwerk/Persistenz behaupten.

### V01 — Referenzdaten und spätere Korrektur prüfen — P0

- [ ] Bestehenden Beispielagenten als nachvollziehbaren Prüfbericht erhalten.
- [ ] Prüfung optional auf alle Agenten und Sensor-IDs ausweiten.
- [ ] Kontrollierten separaten Datenbestand für spätere Testläufe festlegen.
- [ ] Geeignete kleine Regressionstests erst zusammen mit der gewählten Korrektur ergänzen.

**Bereits gemessen:** ID `C0B64FE1-740C-486C-A2D1-00E030269E71`; GT 200 Records,
ABS 199 Records, 100 Sensorzeitpunkte; kein fehlender GT-Join und keine Positionsabweichung;
99 doppelte Schlüssel; erste Geschwindigkeit halbiert; 99 Folgemessungen stimmen mit
Positionsdifferenzen über je 100 ms überein.

**Abnahme:** Dokumentierter Vorher-/Nachher-Vergleich für Positionen, Zeitstempel,
ID-Zuordnung, Duplikate und Intervallgeschwindigkeit. Bestehende Referenzdaten unverändert.
Keine Aussage über sämtliche Runs aus einem einzigen geprüften Agenten ableiten.

## 6. Reproduzierbarkeit und schlanker Experimentbetrieb

### R01 — Messstrom reproduzierbar erzeugen oder wiederverwenden — P0

- [ ] Zufallsquellen inventarisieren: Spawn, Ziele, Geschwindigkeit, Noise, IDs.
- [ ] Zentralen konfigurierbaren Seed und stabile fachliche IDs prüfen.
- [ ] Identischen Messstrom für mehrere Aggregationsvarianten wiederverwenden.
- [ ] Parameter, Zeitbasis und Run-Zuordnung dokumentieren.

**Befund:** Mehrere random_device-/mt19937-Initialisierungen; kein gemeinsamer Seed.
**Abnahme:** Gleicher Seed/Konfiguration ergibt dieselben fachlichen Zustände oder ein
fest gespeicherter Referenzstrom speist alle verglichenen Varianten identisch.
Wall-Clock-Performance muss nicht bitgenau reproduzierbar sein.

### R02 — Wall-Clock-Einfluss auf Bewegung entfernen — P0

- [ ] Aufruf updateVelocity mit simulationRealTime überprüfen und gezielt korrigieren.
- [ ] Fachliche Bewegungszeit von Profiling-/Playback-Zeit trennen.

**Befund:** Agent::updateVelocity verwendet den übergebenen Zeitwert im Noise;
Simulation übergibt derzeit gemessene reale Laufzeit. DB-/CPU-/Renderkosten beeinflussen
so den simulierten Bewegungsverlauf.
**Abnahme:** Identische fachliche Eingaben bleiben bei anderer Verarbeitungs-/Rendergeschwindigkeit gleich.

### R03 — Sicherer Referenzlauf und Ausgabe ohne dauernde DB-Abhängigkeit — P0/P1

- [ ] Experimentdatenbank wählen, bevor der Simulator erneut gestartet wird.
- [ ] clear_database-Verhalten sichtbar dokumentieren und experimentgerecht konfigurieren.
- [ ] Headless von Snapshot-Produktion und DB-I/O entkoppeln, soweit nötig.
- [ ] Minimalen File-/Null-Ausgabepfad oder Offline-Auswertung vorhandener Messungen prüfen.

**Abnahme:** Ein kleiner Vergleich läuft ohne GUI, erzeugt kontrollierte Artefakte und
überschreibt keine Referenzdaten. Ein großes Output-Interface wird nur eingeführt,
wenn mehrere Ausgabepfade es tatsächlich benötigen.

## 7. Simulation und Transport: bekannte technische Prüfaufgaben

### S01 — SharedBuffer-Shutdown und Verbrauch — P0 vor umfangreichen Läufen

- [ ] Wait-Prädikat auf finished/stop und Datenverfügbarkeit prüfen.
- [ ] Ende bei leerer Queue, letztem Frame und früh geschlossenem Renderer prüfen.
- [ ] Unbegrenztes Wachstum bei fehlendem/langsamem Leser messen bzw. begrenzen.
- [ ] Synchronisierung von Agenten-/Sensorsnapshots verschiedener Frequenzen beschreiben.

**Befund:** end benachrichtigt, aber das Wait-Prädikat von read prüft nur eine nichtleere Queue.
Headless produziert weiterhin Snapshots. Ein Zugriffscount von drei ersetzt weder Broadcast
noch Backpressure. Der bestehende read-Aufruf entfernt einen Frame.

**Vorschlag:** Aggregation zunächst im Simulationsthread belassen. Renderer darf ggf.
Frames überspringen; Auswertung muss eventuell alle Batches erhalten. Erst Anforderungen
festlegen, dann Queue/Snapshot-Lösung wählen.
**Abnahme:** Kein Hängen beim Ende und begrenzter Speicher im gewählten Betriebsmodus.

### S02 — Kollisionsgrid und Pointer-Lebensdauer prüfen — P1, vor realistischeren Szenarien

- [ ] width/height initialisieren und Nachbarprüfung validieren.
- [ ] Doppelte Paarprüfung in benachbarten Zellen untersuchen.
- [ ] vector::erase und gespeicherte Agent*-Pointer entkoppeln.
- [ ] Grid-Zuordnung vor/nach Bewegung konsistent festlegen.

**Befund:** Grid-Konstruktor setzt width/height nicht, Nachbarprüfung liest sie;
Löschungen im Agentenvektor können zuvor gespeicherte Pointer invalidieren.
**Abnahme:** Bekannte Nachbarschaften und Agentenaustritte funktionieren ohne ungültige Pointer.
Kein kompletter Kollisionsalgorithmus-Austausch nur zur Behebung dieser Fehler.

### S03 — Quadtree-Speicher und IDs prüfen — P1

- [ ] reset/clear/Destruktor hinsichtlich verlorener Child-Pointer prüfen.
- [ ] Konvention der vier Basiszellen, Depth und Morton-ID dokumentieren.
- [ ] Bounds, Position-to-Cell und Renderer-Rekonstruktion prüfen.

**Befund:** reset setzt Child-Pointer ohne Freigabe auf nullptr. Generische Vollbaumformeln
müssen an die vorhandene Basiszell-Konvention angepasst werden.
**Abnahme:** Nachvollziehbare Ownership und unveränderte gültige IDs; keine neue räumliche
Datenstruktur ohne vorher festgelegte Anforderungen.

## 8. Forschungsfrage, Metriken und Baselines

### E01 — Konkrete Utility-Anwendung festlegen — P0

- [ ] Eine erste Abfrage wählen, etwa zeitlich gemittelte Belegung/Dichte.
- [ ] Referenzraster, Referenzzeitpunkte und Umgang mit unterdrückten/fehlenden Daten festlegen.
- [ ] Fehlermaß gegen GT bestimmen; gleiche Abfrage für alle Varianten verwenden.
- [ ] Auflösung, Datenalter, Coverage und numerischen Fehler getrennt erfassen.

**Abnahme:** Eine feste Frage und ihre GT-Antwort sind definiert. Eine gröbere Ausgabe
bekommt nicht allein durch Anpassung des Referenzrasters automatisch Fehler null.
Record-Retention wird nicht ohne Begründung als Data Fidelity bezeichnet.

### E02 — Angreifer und Privacy-Bewertung festlegen — P0

- [ ] Angriffsziel, Zusatzwissen und sichtbare Veröffentlichungen definieren.
- [ ] Beispiel: Membership Inference anhand aggregierter Belegung; Eignung begründen.
- [ ] Vergleich mit Prior-/No-output-Baseline und einem klaren Erfolgsmaß festlegen.
- [ ] Wiederholte Releases, überlappende Fenster und mögliche Differenzangriffe berücksichtigen.
- [ ] k-Schwelle als Regel von tatsächlich gemessenem Risiko trennen.

**Abnahme:** Ein reproduzierbarer Angreifer mit nachvollziehbarem Wissen und Baseline.
Keine pauschale Anonymitätsbehauptung aus einer Distinct-Agent-Anzahl.

### B01 — Feste Raum-/Zeit-Baselines vergleichen — P0

- [ ] Kleine Auswahl fester Zellgrößen und Zeitfenster festlegen.
- [ ] Gleiche Beobachtungen, Erfassungsbereiche und Abfragen für alle Varianten.
- [ ] Counts und Zeitfenster entsprechend D03 verarbeiten.
- [ ] Utility-Fehler, empirisches Privacy-Maß, Coverage, Datenalter und Laufzeit ausgeben.

**Abnahme:** Reproduzierbare Tabelle/Grafik mit Konfiguration und klaren Grenzen.
Ein erster Vergleich benötigt noch keinen vollständigen Policy-Tree oder realen Stadtplan.

### E03 — Weitere Metriken fachlich auswählen — P1/P2

- [ ] k-/l-/t-/delta-/Entropie-Metriken auf konkrete Daten und Angriffsszenarien prüfen.
- [ ] Sensitive Attribute und Bedeutung von Agentenklassen klären.
- [ ] Mehrere Seeds/Szenarien und sinnvolle statistische Auswertung festlegen.

**Abnahme:** Jede verwendete Metrik hat eine begründete Bedeutung und benötigte interne Daten.
Nicht alle Metriken lassen sich aus Klassen-Counts rekonstruieren.

## 9. Adaptive Aggregation: nächste Entwicklungsstufe

### A01 — Zielzustände und AggregatedCell festlegen — P1

- [ ] Geometrie, Historie, Freigaberegeln und Releases getrennt beschreiben.
- [ ] Sensorlokale Ownership festlegen; Manager ohne MongoDB-Zugriff bevorzugen.
- [ ] Bedeutung aller Count-/Zeit-/Policy-Felder definieren.
- [ ] update(now, tree) gegenüber gebundener Baumreferenz anhand tatsächlicher Anforderungen wählen.

**Abnahme:** Kleine Schnittstelle mit nachvollziehbarer Datenaufnahme und Ausgabe;
keine leere Abstraktionshierarchie als Selbstzweck.

### A02 — Begrenzte Historie und aktive/preemptive Fenster — P1

- [ ] Retrospektive Parent-Aggregation aus internen Messungen spezifizieren.
- [ ] Active/Preemptive-Buckets als Datencontainer oder logische Fensterzustände vergleichen.
- [ ] Aufbewahrungsdauer, offene Fenster und Cleanup definieren.
- [ ] Unterschiedliche Zellfenster und kompatible Merge-Zeitbereiche behandeln.

**Abnahme:** Kein Double Counting, begrenzter Speicher und rekonstruierbare erlaubte Fenster.
Das Löschen eines MongoDB-Records macht eine bereits externe Veröffentlichung nicht rückgängig.

### A03 — Zunächst einfache adaptive Strategien — P1

- [ ] Spatial First und Temporal First mit einer globalen Policy spezifizieren.
- [ ] Sibling-/Parent-/Child-Bedingungen, Merge, Split und Unterdrückung festlegen.
- [ ] Unerfüllbare Constraint-Kombinationen explizit behandeln.
- [ ] Gegen feste Baselines aus B01 vergleichen.

**Abnahme:** Adaptionsentscheidungen sind nachvollziehbar; erlaubte Fenster und Zellansichten
passen zusammen. Ein besserer Privacy/Utility-Trade-off wird gemessen, nicht vorausgesetzt.

### A04 — Regionale Policy-Trees / Applikationsebene — P1

- [ ] Default-, regionale und anwendungsspezifische Constraints definieren.
- [ ] Policy-Tree unabhängig von Datenhierarchie halten.
- [ ] Überschneidungen, Zellen an Grenzen und widersprüchliche Anforderungen behandeln.
- [ ] Mehrere Policy-Views erst nach korrekter einzelner Release-Pipeline prüfen.

**Abnahme:** Keine stillschweigende Abschwächung regionaler Regeln durch räumlichen Merge;
Policy-Konflikte haben eine explizite Auflösung oder Ablehnung.

## 10. Erweiterungen: sichtbar, aber noch nicht im nächsten Arbeitsschritt

- [ ] **X01 — Taxonomie (P1/P2):** Identität/Klasse, Verhalten, Verteilung und Darstellung
  konzeptionell trennen; YAML-Kompatibilität vor Umbau festlegen.
- [ ] **X02 — Heterogene Szenarien (P1):** dichte, dünne, leere und dynamische Bereiche
  reproduzierbar erzeugen; Uniform als Debug-Benchmark erhalten.
- [ ] **X03 — Wege/Trajektorien (P2):** Korridore, Spawn-/Zielbereiche, Wegpunkte;
  reales Routing nur bei Bedarf für Forschungsfrage/Angreiferwissen.
- [ ] **X04 — Karten/Gebäude/Eingänge (P2):** Datenquelle, Koordinaten und notwendige
  Semantik festlegen; UAM-Simulator-Modern als mögliche technische Referenz prüfen.
- [ ] **X05 — Kollisionsmodell (P2):** nach S02 belastbar beurteilen; ORCA o. Ä. nicht
  automatisch als Voraussetzung des Aggregators übernehmen.
- [ ] **X06 — Sensorunsicherheit (P2):** GT unverändert halten, Messfehler separat;
  kein vollständiger Kamera-/LiDAR-Simulator ohne konkreten Bedarf.
- [ ] **X07 — Metal / 3D / GPU (P2):** UAM-Simulator-Modern besitzt den nativen Backend;
  Übernahme erst nach Engpassmessung oder begründetem Visualisierungsbedarf.
- [ ] **X08 — Gemeinsame Bibliotheken/Build (P1/P2):** Duplikate in Simulator/Renderern
  gezielt abbauen; funktionierende getrennte Builds als Referenz bewahren.
- [ ] **X09 — Packaging/Remote (P2):** Repositoryname beibehalten; Remote, Lizenz,
  Veröffentlichung und Daten-/Asset-Auswahl separat festlegen.

## 11. Arbeitsregel für die nächsten Änderungen

Vor dem nächsten Codeeingriff den gewählten TO-DO-Punkt, die Datenregel und den kleinen
Änderungsumfang benennen. Nach dem Eingriff Status, Verifikation und Grenzen aktualisieren.

Aktuell wird ausschließlich dokumentiert. Als nächster Kandidat bietet sich D01/D02
mit anschließendem F01/F02 an. Der Simulator soll dabei schlank bleiben: bestehende
Sensorpipeline korrigieren, statt für die zwei ABS-Fehler das gesamte System umzubauen.
