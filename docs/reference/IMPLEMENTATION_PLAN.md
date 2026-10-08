# Implementierungsplan – Adaptive Privacy-Preserving Urban Mobility Data Aggregation

**Projekt:** Dissertation – Adaptive, Metric-Based and Privacy-Preserving Urban Mobility Data Sharing  
**Technologie:** C++17, SFML, OpenGL, MongoDB  
**Architektur:** Agent-Based Simulation mit sensorlokaler Aggregation  
**Ziel:** Wissenschaftlich evaluierbares Framework für adaptive räumliche und zeitliche Datenaggregation unter regionalen Privacy- und Utility-Constraints.

> **Leitprinzip:** Ein maximal aufgelöster interner Datenbestand, aus dem unter Privacy-, Utility- und Anwendungsconstraints dynamisch zulässige räumlich-zeitliche Veröffentlichungen erzeugt werden.
>
> **Wichtige Abgrenzung:** Detektion und Klassifizierung sind nicht Forschungsgegenstand. Ground Truth bleibt erhalten; Messunsicherheit kann als eigene Sensorschicht modelliert werden. Die zentrale Herausforderung ist die korrekte zeitliche Historie bei variabler räumlicher Aggregation.

## Prioritäten

| Priorität | Bedeutung |
|---|---|
| **P0** | Notwendige Kernfunktionalität |
| **P1** | Wichtig für Evaluation und Dissertation |
| **P2** | Erweiterung, die die Kernimplementierung nicht blockieren darf |
| **P3** | Zukunftsperspektive außerhalb des aktuellen Forschungsumfangs |

---

# 1. Grundlegende Zielarchitektur

## 1.1 Gesamtstruktur

Die bestehende Simulation besitzt einen internen Agentenvektor sowie einen Vektor verschiedener Sensorinstanzen. Die Sensoren verarbeiten die Agentenzustände und erzeugen unterschiedliche Datendarstellungen. **Diese Grundstruktur erhalten.**

```text
                         SIMULATION
                   ┌───────────────────┐
                   │ Agent Management  │
                   │ Ground Truth      │
                   │ Trajectories      │
                   └─────────┬─────────┘
                             │
                     std::vector<Agent>
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
          AgentBased     GridBased    AdaptiveGridBased
            Sensor         Sensor          Sensor
               │             │             │
               │             │             ▼
               │             │        Sensor Model
               │             │             │
               │             │             ▼
               │             │        Max-Quadtree
               │             │             │
               │             │             ▼
               │             │       Temporal Storage
               │             │             │
               │             │             ▼
               │             │       AggregationManager
               │             │             │
               │             │             ▼
               │             │       Policy Evaluation
               │             │             │
               │             │             ▼
               │             │       Published Cells
               │             │             │
               └─────────────┼─────────────┘
                             ▼
                   Sensor Output / MongoDB
                             │
                             ▼
                        SharedBuffer
                             │
                             ▼
                          Renderer
```

**Architekturentscheidung:** Der `AggregationManager` ist eine Komponente der Pipeline des jeweiligen `AdaptiveGridBasedSensor`, **keine globale Instanz**. Jeder adaptive Sensor besitzt grundsätzlich eigenen Erfassungsbereich, Quadtree, temporären Messbestand, AggregationManager, Policies/Policy-Zuordnungen und Veröffentlichungsschnittstelle. Zentrale Multi-Sensor-Fusion bleibt eine spätere Option.

## 1.2 Verantwortlichkeiten

| Komponente | Verantwortung |
|---|---|
| `Simulation` | Agenten erzeugen, bewegen und aktualisieren |
| `Sensor` | Sensorpipeline koordinieren und Ergebnisse veröffentlichen |
| `AgentBasedSensor` | Agentenbasierte Referenzdaten |
| `GridBasedSensor` | Statisches Grid als Benchmark |
| `AdaptiveGridBasedSensor` | Adaptive räumlich-zeitliche Aggregation |
| `SensorModel` | Abstrakte Messunsicherheit und Sensorparameter |
| `Quadtree` | Räumliche Hierarchie und Zellgeometrie |
| `TemporalStorage` | Messhistorie und zeitliche Datenfenster |
| `AggregationManager` | Aggregationsentscheidungen und Ausgabeplanung |
| `PolicyManager` | Regionale Regeln und Constraints |
| `MetricEvaluator` | Privacy-, Utility- und Systemmetriken |
| `SharedBuffer` | Threadübergreifender Datenaustausch |
| `Renderer` | Visualisierung |
| MongoDB-Adapter | Persistenz/Übertragung der Sensorergebnisse |

**Grundregel:** Jedes Modul übernimmt nur seine klar definierte Verantwortung.

---

# 2. Phase 0 – Code-Audit und Bestandsaufnahme

**Priorität: P0**

Vor jeder Änderung den tatsächlichen Code lesen. Nicht direkt große Klassen umschreiben.

## Vorhandene Dateien

```text
Main.cpp
Simulation.hpp / Simulation.cpp
Renderer.hpp / Renderer.cpp
Region.hpp / Region.cpp
Quadtree.hpp / Quadtree.cpp
Sensor.hpp / Sensor.cpp
AdaptiveGridBasedSensor.hpp / AdaptiveGridBasedSensor.cpp
GridBasedSensor.hpp / GridBasedSensor.cpp
AgentBasedSensor.hpp / AgentBasedSensor.cpp
AggregationManager.hpp / AggregationManager.cpp
SharedBuffer.hpp / SharedBuffer.tpp
```

Weitere Repository-Dateien/Abhängigkeiten berücksichtigen.

### 2.1 Datenflüsse analysieren

- Agentenerzeugung und -aktualisierung.
- Verwaltung von Sensorinstanzen.
- Zuordnung der Messdaten zu Quadtree-Zellen.
- Derzeitiges Splitting, Merging und maximale Tiefe.
- Cell-ID-Konvention und Zellrekonstruktion.
- MongoDB-Publishing je Sensor.
- SharedBuffer zwischen Simulation und Renderer.

### 2.2 Ownership und Threading dokumentieren

- Wer besitzt Quadtree, Sensoren und SharedBuffers?
- Wo werden Daten kopiert, wo Referenzen/Pointer verwendet?
- Welche Komponenten laufen in welchen Threads?
- Wie werden Simulations- und Renderzeit synchronisiert?

### 2.3 Referenzzustand bewahren

Vor Refactoring reproduzierbaren Referenzlauf und Tests sichern. Bestehende Sensorvarianten und Visualisierung funktionsfähig halten.

**Ergebnis:** Dokumentierter Ist-Zustand mit Klassenhierarchie, Datenfluss, Architekturproblemen, Änderungsliste pro Datei, Test-/Migrationsstrategie.

---

# 3. Phase 1 – Quadtree-Architektur überarbeiten

**Priorität: P0**

## 3.1 Vollständig aufgelöster, statischer Quadtree

**Bisher:** Dynamische Splits anhand eingehender Agentenpositionen; leere Bereiche bleiben teils ungesplittet.  
**Zukünftig:** Die räumliche Topologie wird **einmal bei der Initialisierung** bis zur maximalen Tiefe aufgebaut und danach nicht verändert.

```text
Quadtree initialization
    → Build full tree
    → Fixed spatial hierarchy
    → Measurement assignment
    → Aggregation and policy evaluation
    → Dynamic publication view
```

- Keine strukturellen Splits oder Merges im regulären Betrieb.
- Alle Parent-/Child-Knoten bleiben bestehen.
- Ein räumlicher Merge erzeugt eine **aggregierte Parent-Repräsentation**, verändert aber nicht die Topologie.
- Renderer erhält nur veröffentlichte Cell-IDs und rekonstruiert Geometrie daraus; leere Max-Depth-Zellen müssen nicht gezeichnet werden.

## 3.2 Maximale Tiefe konfigurierbar machen

Parameter:

```text
simulation_width
simulation_height
maximum_tree_depth
minimum_cell_size
```

Für quadratische Wurzelzelle der Kantenlänge `L`:

\[
s(d)=\frac{L}{2^d}
\]

Für die Anforderung „Zellgröße **höchstens** `s_target`“:

\[
d=\left\lceil \log_2\left(\frac{L}{s_{target}}\right)\right\rceil
\]

Soll eine physikalische **Mindestgröße nicht unterschritten** werden, muss die Tiefe anders begrenzt werden. Anforderungen unterscheiden und im Code nicht verwechseln.

## 3.3 Cell-IDs stabil halten

- Jede Zelle: eindeutige ID und Tiefe.
- Parent-ID und Child-IDs effizient bestimmbar.
- Bounds aus ID ableitbar.
- Vorhandene Konvention beibehalten:

```text
0 = North-West
1 = North-East
2 = South-West
3 = South-East
```

Cell-IDs sind die Schnittstelle für Aggregation, Speicherung, Renderer, MongoDB, Metriken und Policy-Zuordnung.

## 3.4 Speicherbedarf und Datenstrukturen

Vollständiger Quadtree mit maximaler Tiefe `D`:

\[
N_{nodes}=\frac{4^{D+1}-1}{3}
\]

| Maximale Tiefe | Gesamte Knoten |
|---|---:|
| 5 | 1.365 |
| 7 | 21.845 |
| 8 | 87.381 |
| 10 | 1.398.101 |
| 12 | 22.369.621 |

**Empfehlung:** Statische räumliche **Topologie** und **zeitliche Messdaten** voneinander trennen. Die Topologie kann voll materialisiert sein; temporäre Daten werden nur für relevante Zellen angelegt.

Beispielhafte Struktur (an Bestandscode anpassen):

```cpp
struct QuadtreeNode {
    CellId id;
    CellId parentId;
    std::array<CellId, 4> children;
    AABB bounds;
    uint8_t depth;
};
```

## 3.5 Bottom-up-Aggregation

```text
Leaf 0: 2 Agents
Leaf 1: 3 Agents
Leaf 2: 1 Agent
Leaf 3: 4 Agents
→ Parent: 10 Messbeiträge
```

Aggregierbare Informationen: Counts, Klassenhäufigkeiten, Geschwindigkeiten, Zeitintervalle und ggf. Agentenidentitäten für die interne Privacy-Prüfung. **Counts sind additiv; Mengen unterschiedlicher Personen nicht zwangsläufig.** Bei mehrfachen Beobachtungen eines Agenten korrekt deduplizieren.

**Abnahmekriterien:** Topologie unverändert; Position-to-Leaf korrekt; Parent-Aggregation korrekt; stabile IDs; keine doppelte Zählung; dokumentierter Speicherbedarf.

---

# 4. Phase 2 – Temporale Datenhaltung entwickeln

**Priorität: P0**

Die zeitliche Aggregation soll von der räumlichen Struktur unabhängig sein. Hier liegen die wichtigsten Designentscheidungen.

## 4.1 Konzeptgeschichte

Bisher: `active bucket` und `buffer bucket` für normale und *pre-emptive aggregation*. Neu: Retrospektive Rekonstruktion beliebiger zulässiger Parent-Fenster aus maximal aufgelösten Messdaten. Prüfen, ob zwei physische Buckets hierfür ausreichen oder ein allgemeinerer zeitlicher Speicher sinnvoller ist.

## 4.2 Anforderungen

1. Zeitgestempelte Messungen aufnehmen.
2. Variable Aggregationsfenster erlauben.
3. Fenster verlängern.
4. Räumliche Parent-Fenster rückwirkend rekonstruieren.
5. Historie begrenzt halten und sicher aufräumen.
6. Zellindividuelle Fenster erlauben.
7. Veröffentlichungszeitpunkt erfassen.

**Invariante:** Für jedes erlaubte Zeitfenster muss die zugehörige Parent-Aggregation aus relevanten Child-/Leaf-Daten rekonstruierbar sein.

## 4.3 Zeitbins / Ringbuffer

Beispiel:

```text
Leaf Cell 104
0ms     100ms     200ms     300ms     400ms
[B0]────[B1]──────[B2]──────[B3]──────[B4]

100 ms → [B0]
300 ms → [B0+B1+B2]
500 ms → [B0+B1+B2+B3+B4]
```

Zeitlich geordnete Bins bzw. begrenzter Ringbuffer sind eine zu prüfende Grundlage, keine ungeprüft festgeschriebene Implementierung.

## 4.4 Active und Buffer Buckets

- **Active:** Daten des aktuell offenen Fensters.
- **Buffer:** Vorbereitung des nächsten Fensters oder klar definierte Preemptive-Strategie.
- **Historische Bins:** retrospektive zeitliche und räumliche Aggregation.

Prüfen, ob Active/Buffer als **logische Fensterzustände** über einem gemeinsamen Zeitdatenspeicher geführt werden können, statt Daten redundant pro Node zu duplizieren.

## 4.5 Fenstermanagement

Muss für jeden relevanten Bereich definieren: Beginn, Ende, Verlängerung, Abschluss, Veröffentlichung, Verwerfung.

```text
Cell A: 100 ms
Cell B: 300 ms
Cell C: 700 ms
Cell D: 1000 ms
```

Bei Merge benachbarter Zellen muss eine kompatible zeitliche Grundlage sichergestellt werden. Keine Beiträge außerhalb des gewählten Fensters und keine doppelte Zählung über überlappende oder bereits veröffentlichte Intervalle.

## 4.6 Retention

Konfiguration:

```text
history_retention_ms
minimum_aggregation_window_ms
maximum_aggregation_window_ms
time_bin_size_ms
```

Messungen erst endgültig entfernen, wenn keine erlaubte offene Aggregation sie benötigt.

**Abnahmekriterien:** Dynamische Fenster, retrospektive Parents, keine doppelten Beiträge, begrenzter Speicher, zellindividuelle Fenster.

---

# 5. Phase 3 – Policy-System implementieren

**Priorität: P0**

Regionale Anwendungsregeln begrenzen die erlaubte Veröffentlichungsgranularität und Datenschutzanforderungen.

## 5.1 Profile / Anwendungsfälle

| Anwendung | Beispielhafte Anforderungen |
|---|---|
| Verkehrsflussanalyse | Gute zeitliche, ggf. grobere räumliche Auflösung |
| Stadtplanung | Gröbere räumliche/zeitliche Aggregation |
| Einzelhandelsanalyse | Regionale Besuchsstatistiken |
| Behördliche Auswertung | Zweckgebundene Granularität |
| Polizeiliche Suche | Separat zu definierende Zugriffs-/Datenschutzregeln |

Es handelt sich um **Forschungsszenarien**, nicht um Behauptungen zu rechtlichen Zugriffsberechtigungen.

## 5.2 Datenmodell

```text
PolicyManager
Policy
PolicyRegion
PolicyConstraints
```

Beispiel:

```cpp
struct PolicyConstraints {
    uint32_t minK;
    uint8_t minDepth;
    uint8_t maxDepth;
    double minTemporalWindow;
    double maxTemporalWindow;
    double maxStaleness;
};
```

Modulare Erweiterung um weitere Privacy-/Utility-Kriterien.

## 5.3 Regionale Zuordnung

Mögliche Formen: AABBs, Polygone, unabhängiger Policy-Overlay-Tree. **Policy-Tree und Daten-Quadtree konzeptionell unabhängig halten.** Änderungen an Policies sollen keine Rekonstruktion der Sensortopologie verlangen.

## 5.4 Überlappungen und Konflikte

- Globale Defaults und regionale Overrides.
- Überlappende Policy-Regionen.
- Zellen über mehrere Regionen.
- Widersprüchliche Anforderungen.
- Merges über Policy-Grenzen hinweg.

Konflikte entweder explizit zurückweisen oder über dokumentierte Regel auflösen. **Niemals durch Merge stillschweigend schwächere Anforderungen anwenden.**

## 5.5 Änderungen zur Laufzeit — P1

Neue Regeln dürfen zukünftige Aggregationen beeinflussen; bereits veröffentlichte Daten sind nicht rückholbar.

**Abnahmekriterien:** Globale/regionale Policies, deterministische Konfliktbehandlung, vollständige Constraint-Erfüllung vor Veröffentlichung, unabhängig vom Quadtree.

---

# 6. Phase 4 – AggregationManager vollständig implementieren

**Priorität: P0 – höchste fachliche Bedeutung**

Verknüpft Quadtree, Historie, Privacy/Utility, Policies und Aggregationsstrategien.

## 6.1 Aufgaben

1. Eingangsmessungen bewerten.
2. Kandidaten für räumliche/zeitliche Aggregation bilden.
3. Privacy- und Utility-Constraints prüfen.
4. Räumliche und zeitliche Aggregation ausführen.
5. Konfigurierte Strategie anwenden.
6. Freigeben, zurückhalten oder endgültig unterdrücken.
7. Evaluierungsmetriken aktualisieren.

## 6.2 Spatial First

```text
Constraint violated
    → Merge spatial cells
    → Reevaluate
    → If needed: extend temporal window
```

Ziel: Frische Daten bevorzugen, räumlich vergröbern.

## 6.3 Temporal First

```text
Constraint violated
    → Extend temporal window
    → Reevaluate
    → If needed: merge spatial cells
```

Ziel: Räumliche Details nach Möglichkeit behalten.

## 6.4 Metric-Based Adaptive — P1

Mehrere Kandidaten vergleichen, nur zulässige Kombinationen berücksichtigen.

\[
U=f(U_{spatial},U_{temporal},U_{latency},U_{fidelity})
\]

Unter geeigneten Privacy- und Utility-Nebenbedingungen. Konfigurierbare Zielfunktion/Priorisierung; keine stillschweigende Annahme, dass immer eine zulässige Lösung existiert.

## 6.5 Veröffentlichung

```text
Input Measurements
    → Temporal Storage
    → Generate Candidates
    → Evaluate Constraints
         ├─ Valid   → Publish
         └─ Invalid → Spatial/Temporal Adaptation
                         → Reevaluate
                              ├─ Valid → Publish
                              └─ Invalid → More aggregation possible?
                                             ├─ Yes → Repeat
                                             └─ No  → Suppress
```

## 6.6 Keine redundanten Veröffentlichungen

Vermeide gleichzeitige widersprüchliche Parent-/Child-Veröffentlichungen im selben Ausgabeintervall, die Beiträge doppelt zählen oder Rückschlüsse durch Differenzbildung ermöglichen. Berücksichtige auch wiederholte Releases und überlappende Zeitfenster als Privacy-Risiko.

## 6.7 Policy-spezifische Views — P1

Perspektivisch: gemeinsamer interner Messbestand, aber getrennte Policy-Auswertung und Veröffentlichungszustände. Zunächst **eine aktive Veröffentlichungspolicy pro Sensor**, alternative Policies in separaten, identisch gespeisten Experimenten.

**Abnahmekriterien:** Spatial First, Temporal First, korrekte Unterdrückung, keine ungültigen Releases oder unbeabsichtigte Doppelveröffentlichung, reproduzierbare Entscheidungen.

---

# 7. Phase 5 – Privacy-Metriken

**Priorität: P0/P1**

Unabhängig austauschbare Evaluatoren.

## 7.1 k-Anonymity / k-basierte Mindestanzahl — P0

\[
k(c,W)=\left|\{\text{distinct agents in }(c,W)\}\right|
\]

Mehrfachbeobachtungen derselben Person nicht mehrfach zählen. **Wissenschaftlich sauber abgrenzen:** Eine Mindestanzahl eindeutiger Agenten ist zunächst eine operative k-basierte Freigaberegel; für formale k-Anonymität müssen Angreifermodell, Quasi-Identifikatoren und Verknüpfbarkeit mehrerer Veröffentlichungen spezifiziert werden.

## 7.2 l-Diversity — P1

Verschiedene relevante Merkmalsausprägungen im Aggregat; Agententypen sind nicht automatisch geeignete sensitive Attribute. Semantik explizit definieren.

## 7.3 Weitere Metriken — P2

- t-Closeness
- δ-Presence
- Entropy
- KL-Divergence
- Mutual Information

Modularer Aufbau:

```text
PrivacyMetricEvaluator
  ├── KAnonymity
  ├── LDiversity
  ├── TCloseness
  ├── DeltaPresence
  └── InformationMetrics
```

Nicht alle Metriken sind aus bloßen Klassen-Counts rekonstruierbar. Benötigte Informationen je Metrik dokumentieren.

---

# 8. Phase 6 – Utility- und Systemmetriken

**Priorität: P0/P1**

## 8.1 Spatial Resolution — P0

Veröffentlichte Zellkante, Zellfläche, Tiefe und ggf. mittlere effektive räumliche Granularität.

## 8.2 Temporal Resolution — P0

\[
\Delta t=t_{end}-t_{start}
\]

Pro veröffentlichtem Aggregat.

## 8.3 Temporal Lag / Data Staleness — P0

\[
L=t_{publication}-t_{latestMeasurement}
\]

**Nur Zeitpunkte gleicher Zeitbasis subtrahieren.** Getrennt erheben: Simulationszeit-basiertes Datenalter und Wall-Clock-Verarbeitungslatenz.

## 8.4 Processing Time — P0

\[
T_{processing}=t_{end}-t_{start}
\]

- Global je Update/Batch.
- Pro Zelle je Aggregationsentscheidung.
- Bei überlappenden Berechnungen inklusive/exklusive Laufzeiten unterscheiden.
- Zusätzliche Zähler: geprüfte Zellen, Merges, Fensterverlängerungen, Constraint-Checks.

## 8.5 Data Fidelity / Suppression Rate — P0

\[
F=1-\frac{N_{suppressed}}{N_{input}}
\]

**Vergleiche Messbeiträge, nicht bloß die Anzahl aggregierter MongoDB-Records.** Erfassen: `InputMeasurements`, `PublishedContributions`, `SuppressedContributions`, `SuppressionReasons`. Ein veröffentlichter Record kann viele Input-Messungen repräsentieren.

## 8.6 Localization Accuracy — P1

Vergleich GT vs. gemessener Position und separat vs. veröffentlichter Zellrepräsentation (z. B. Mittelpunkt). Sensorfehler und Aggregationsfehler getrennt ausweisen.

## 8.7 Classification Accuracy — P1

Nur aussagekräftig bei aktivem Klassifikationsfehlermodell. Direkt aus Ground Truth übernommene Labels haben definitionsgemäß 100 % simulierte Genauigkeit und sind kein eigenständiges Forschungsergebnis.

## 8.8 Weitere Metriken — P1/P2

- Velocity Error
- OD-Flows / Flow Preservation
- Class Distribution Error
- Aggregation Overhead
- Memory Consumption
- CPU Utilization
- Publication Rate

---

# 9. Phase 7 – Sensor-Modell und Messunsicherheit

**Priorität: P1**

Detektion/Klassifikation selbst gehören nicht zur Arbeit. **Keinen vollständigen Kamera-/LiDAR-Simulator entwickeln.**

## 9.1 Ground Truth getrennt halten

```text
Ground Truth Position
    → Sensor Measurement Model
    → Measured Position
    → Quadtree
```

Ground Truth niemals durch Sensorrauschen überschreiben.

## 9.2 LiDAR-orientiertes Modell

Parameter:

```text
sensor_position
sensor_orientation
horizontal_fov
vertical_fov
maximum_range
beam_divergence
angular_sampling_resolution
range_noise_sigma
angular_noise_sigma
```

**Beam Divergence ≠ Winkelabstand der Messstrahlen ≠ Winkelrauschen.** Nicht unmittelbar aus Divergenz auf Standardabweichung schließen.

Beispiel im Polarkoordinatensystem:

\[
r_m=r_{GT}+\epsilon_r,\qquad \theta_m=\theta_{GT}+\epsilon_\theta
\]

Dann Rücktransformation nach kartesisch; dadurch distanz- und richtungsabhängiger Fehler.

## 9.3 Kamera-Klassifikation — P1

Zunächst GT-Klasse als Label. Optional Confusion Matrix, klassenspezifische Fehlerraten und Detektionswahrscheinlichkeit. Keine echten CNNs nötig.

## 9.4 Sensorfusion — P2

Konzeptionelle Erweiterungen: LiDAR + Monokamera, Stereo oder LiDAR + Stereo. Vollständige Fusion für Kernalgorithmus nicht erforderlich.

## 9.5 Distanzabhängige Auflösung — P1

Trennen: Sensorauflösung, Lokalisierungsunsicherheit, Anwendungsanforderung, maximale Quadtree-Tiefe. Sensorbedingte Mindestgranularität ggf. **über Policies/Utility-Constraints** berücksichtigen, statt die statische Topologie je Entfernung umzubauen.

---

# 10. Phase 8 – SharedBuffer und Threading

**Priorität: P0**

## 10.1 Interne Container vs. Threadgrenzen

`Simulation` hält den Agentenvektor und die Sensorinstanzen. Sensoren lesen diese Zustände im selben Ausführungskontext direkt. **SharedBuffers sind für Austausch zwischen Threads**, nicht für jeden internen Methodenaufruf.

## 10.2 Sim → Renderer

```text
Simulation Thread → SharedBuffer → Renderer Thread
```

Renderer braucht agentenbasierte Debug-Ansicht und aggregierte Sensoransichten. Keine unsynchronisierten Mutationen über Threadgrenzen.

## 10.3 CombinedFrame — P1

```cpp
struct CombinedFrame {
    double simulationTime;
    std::vector<AgentVisualization> agents;
    std::vector<SensorVisualization> sensors;
};
```

Bestehende Implementierung möglichst über unveränderliche Snapshots adaptieren. Sensoren publizieren nicht zwangsläufig pro Simulationstick: pro Sensor Erfassungszeit, Fenster, Publikationszeit, Sequenznummer erfassen.

## 10.4 Immutable Snapshots — P1

Prüfen, ob bestehende `SharedBuffer` sinnvoll mit `std::shared_ptr<const T>` arbeitet: geringe Kopierlast, klare Ownership, konsistente Snapshots, keine Data Races.

## 10.5 Eigener Aggregator-Thread — P2

Zunächst Sensorpipeline/Aggregation im Simulationsthread. Separaten Thread erst nach Performance-Messung erwägen, ggf. immutable Measurement-Batches über Queue.

## 10.6 Unix Domain Socket — P3

Nur optional für getrennte Prozesse und Crash-Isolation bzw. austauschbare Pipelines. Nicht für den aktuellen In-Process-Fall erforderlich.

---

# 11. Phase 9 – MongoDB und Sensor-Output

**Priorität: P0/P1**

**Der Sensor ist Eigentümer der Veröffentlichungslogik und MongoDB-Kommunikation.** Der AggregationManager selbst kennt MongoDB nicht.

```text
AdaptiveGridBasedSensor
    → AggregationManager
    → Aggregated Cells
    → Sensor Output Interface
         ├── MongoDB
         ├── SharedBuffer
         └── Optional File Export
```

## 11.1 Datensätze

```cpp
struct AggregatedCell {
    CellId cellId;
    double windowStart;
    double windowEnd;
    uint32_t totalCount;
    ClassCounts classCounts;
};
```

Weitere Felder: `sensor_id`, `policy_id`, `publication_timestamp`, `aggregation_strategy`, `spatial_depth`. Interne Agentenidentitäten **nicht** mit veröffentlichen. Evaluierungsdaten gegebenenfalls getrennt speichern.

## 11.2 Output-Interface — P1

```text
ISensorOutput
   ├── MongoOutput
   ├── FileOutput
   └── NullOutput
```

Damit Benchmarks ohne externe Datenbank ausführbar sind.

## 11.3 Asynchrones Publishing — P1

Gegebenenfalls begrenzte Queue, sodass DB-I/O Aggregation nicht blockiert. Zeitpunkte getrennt messen: Aggregationsabschluss, Queue-Übergabe, erfolgreiche Persistenz.

---

# 12. Phase 10 – Simulation und Agentenverteilung verbessern

**Priorität: P1**

## 12.1 Homogene Verteilung als Benchmark erhalten

Uniform Distribution ist nützlich für Debugging, Skalierung, reproduzierbare Referenztests.

## 12.2 Heterogene Szenarien

Konfigurierbare Bereiche: `Dense`, `Medium`, `Sparse`, `Empty`. Parameter: Spawn Rate, Target Density, Class Distribution, Region Bounds.

## 12.3 Spawn Areas — P1

Statt rein zufälliger Startpositionen optional Gebäudeeingänge, Straßen, Fußwege, Haltestellen, Plätze.

## 12.4 Target Areas — P1

Gebäudeeingänge, Ausgänge, Haltestellen, Kreuzungen, Zielkorridore; erzeugt plausiblere Bewegungsflüsse.

## 12.5 Path Planning — P2

Wegpunkte, Routen, Hindernisvermeidung, agentenspezifische Geschwindigkeiten, ggf. ORCA. Darf den Kernaggregator nicht blockieren.

## 12.6 Agentenklassen — P1

Bestehende Typen erhalten und bei Bedarf erweitern: Pedestrian, Cyclist, Scooter, Wheelchair User, andere VRUs. Später differenzierte Taxonomie mit Basisgruppe, Modalität und Mobilitätseinschränkungen.

---

# 13. Phase 11 – Renderer überarbeiten

**Priorität: P1**

## 13.1 Zellrekonstruktion

Renderer erhält **nur veröffentlichte Cell-IDs und zugehörige Aggregationswerte**, rekonstruiert Bounds und zeichnet diese. Vollständig gesplitteter interner Baum muss **nicht** gezeichnet werden.

## 13.2 Ansichten erhalten

- Agent View: Ground Truth und Trajektorien.
- Static Grid View: Benchmark.
- Adaptive Grid View: tatsächliche veröffentlichte Cells.

## 13.3 Aggregationsvisualisierung — P1

Zellgrößen, räumliche Merges, temporale Fenster, Privacy-Konformität, Suppression, regionale Policy-Constraints; ggf. Overlays für räumliche Tiefe, Zeitfenster und Privacy-Status.

## 13.4 Policy-Overlay — P1

Policy-Regionen transparent über Karte legen und regionale Adaptivität prüfen.

## 13.5 OpenGL-/3D-Renderer — P2

SFML/OpenGL separat verbessern (macOS-Grenze: OpenGL 4.1 Core Profile). Kernsystem bleibt mit 2D-Renderer vollständig nutzbar.

---

# 14. Phase 12 – Evaluation Framework

**Priorität: P1**

Evaluation direkt in Architektur integrieren, statt ausschließlich Mongo-Dumps manuell auszuwerten.

## 14.1 Reproduzierbare Konfiguration

```yaml
simulation:
  width: 120
  height: 60
  duration: 300
  timestep: 0.05
  agents: 100
  random_seed: 42

quadtree:
  max_depth: 5

aggregation:
  strategy: spatial_first
  min_window_ms: 100
  max_window_ms: 1000

privacy:
  k: 5

sensor:
  noise_enabled: false
```

Beispielwerte, keine final festgelegten experimentellen Parameter. `0.05 s` Zeitschritt entspricht **20 Updates/s**.

## 14.2 Szenarien

| Szenario | Zweck |
|---|---|
| Uniform Density | Referenz/Skalierung |
| Dense Region | Hohe Dichte |
| Sparse Region | Privacy in dünn belegten Räumen |
| Mixed Density | Heterogene Bedingungen |
| Dynamic Density | Zeitlich veränderliche Verteilung |
| Regional Policies | Unterschiedliche Constraints |
| Strict Privacy | Hoher Aggregationsdruck |
| Sensor Noise | Unsicherheitsauswirkung |

## 14.3 Baselines

1. Agent-Based Reference.
2. Static Grid Aggregation.
3. Spatial-Only Aggregation.
4. Temporal-Only Aggregation.
5. Spatial-First.
6. Temporal-First.
7. Metric-Based Adaptive.

Fehlende Baselines implementieren oder begründet ausklammern.

## 14.4 Metriken

```text
Privacy Compliance
Spatial Resolution
Temporal Resolution
Data Staleness
Processing Time
Data Fidelity
Localization Error
Velocity Error
Publication Rate
Suppression Rate
Memory Usage
CPU Usage
```

## 14.5 Headless Experiment-Runner

Konfiguration laden, deterministischen Lauf starten, Metriken/exportierte Daten speichern:

```text
experiment_001/
  config.yaml
  metadata.json
  metrics.csv
  publications.csv
```

## 14.6 Statistik

Mehrere Random Seeds; Mittelwert, Median, Standardabweichung, Quantile und ggf. Konfidenzintervalle. Keine wissenschaftlichen Schlussfolgerungen aus einem einzelnen Run.

---

# 15. Phase 13 – Tests und wissenschaftliche Korrektheit

**Priorität: P0/P1**

## 15.1 Quadtree

IDs, Parent/Child, Bounds, vollständige Initialisierung, Mapping, unveränderliche Topologie.

## 15.2 Temporal Storage

Fensterstart, -verlängerung, -abschluss; Rückwärtsaggregation; Cleanup; Überlappungen; wiederholt beobachtete Agenten.

## 15.3 Privacy

```text
Cell distinct agents = 3, k = 5 → no publication
Parent distinct agents = 8, k = 5 → publication permitted,
                                  sofern alle anderen Constraints erfüllt
```

## 15.4 Policy

Zwei Regionen; Überschneidungen; Konflikte; Merge über Regionsgrenzen; unerfüllbare Anforderungen.

## 15.5 Aggregation

Spatial First, Temporal First, Suppression, keine doppelte Zählung, korrekte Parent-Statistik, dokumentierte Verlustursachen.

## 15.6 Reproduzierbarkeit

Identischer Seed + Konfiguration → fachlich identische Entscheidungen. Wall-Clock-Performance muss nicht bitgenau reproduzierbar sein.

---

# 16. Phase 14 – Performance und Skalierbarkeit

**Priorität: P1**

**Erst Korrektheit, dann Optimierung.**

## 16.1 Profiling

Quadtree-Zugriff, Leaf-Mapping, temporale Datenhaltung, Parent-Aggregation, Policy-Lookup, Metrics, Publishing.

## 16.2 Optimierungen prüfen

- Zusammenhängender Node-Speicher.
- Indizes statt Pointer-Chasing.
- Vorberechnete Parent-/Child-Verbindungen.
- Listen aktiver Zellen.
- Inkrementelle Statistiken.
- Begrenzte Ringbuffer.

## 16.3 Nur aktive Bereiche verarbeiten

Vollständige statische Topologie muss nicht bei jedem Tick vollständig traversiert werden; ggf. aktive Leaves und ihre Vorfahren nutzen.

## 16.4 Speicher separat bilanzieren

Topologie, Historie, Privacy-Hilfszustände, Queue, SharedBuffers.

## 16.5 Laufzeitkosten aufschlüsseln

Simulation, Sensor, Aggregation, Policy-Evaluation, Veröffentlichung, Datenbanktransfer. Keine ungemessenen Performance-Versprechen.

---

# 17. Phase 15 – Erweiterungen außerhalb des kritischen Pfads

**Priorität: P2/P3**

| Feature | Priorität | Beschreibung |
|---|---|---|
| LiDAR-/Kamera-Fusion | P2 | Weitergehende Sensorunsicherheit |
| Vollständige Stereo-Simulation | P3 | Kamera-Tiefenrekonstruktion mit Baseline |
| ORCA Collision Avoidance | P2 | Realistische Bewegungen |
| OSM-/CityGML-Import | P2 | Stadtgeometrie |
| Gebäude-/Eingangsmodell | P2 | Semantische Start-/Zielbereiche |
| 3D-Renderer | P2 | Zusätzliche Visualisierung |
| Multi-Sensor-Fusion | P3 | Gemeinsame Messbasis |
| Zentraler AggregationManager | P3 | Mehrere Sensoren |
| Unix Domain Socket | P3 | Prozessübergreifende Kommunikation |
| GPU-Beschleunigung | P3 | Performance |
| Distributed Processing | P3 | Verteilte Architektur |
| Erweiterte Privacy-Metriken | P2 | Weitere formale Kriterien |

---

# 18. Konkrete Implementierungsreihenfolge

| Schritt | Aufgabe | Priorität | Voraussetzung |
|---|---|---|---|
| 1 | Code-Audit und Architektur dokumentieren | P0 | Keine |
| 2 | Tests und Referenzläufe sichern | P0 | 1 |
| 3 | Topologie von Messdaten trennen | P0 | 2 |
| 4 | Statischen Max-Quadtree implementieren | P0 | 3 |
| 5 | Cell-ID-/Parent-Aggregation testen | P0 | 4 |
| 6 | Temporale Datenhaltung implementieren | P0 | 5 |
| 7 | Retrospektive Aggregation ermöglichen | P0 | 6 |
| 8 | Policy-Datenmodell implementieren | P0 | 4 |
| 9 | Policy-Overlay und regionale Zuordnung | P0 | 8 |
| 10 | k-basierte Privacy-Prüfung | P0 | 6, 8 |
| 11 | AggregationManager: Spatial First | P0 | 7–10 |
| 12 | AggregationManager: Temporal First | P0 | 11 |
| 13 | Veröffentlichung und Suppression | P0 | 12 |
| 14 | Sensorpipeline vollständig integrieren | P0 | 13 |
| 15 | MongoDB-Output erhalten und entkoppeln | P0/P1 | 14 |
| 16 | SharedBuffer und Renderer integrieren | P0 | 14 |
| 17 | Basis-Utility-Metriken implementieren | P0 | 13 |
| 18 | End-to-End-Tests | P0 | 14–17 |
| 19 | Heterogene Agentenverteilungen | P1 | 18 |
| 20 | Sensorrauschen | P1 | 18 |
| 21 | Metric-Based Adaptive Strategy | P1 | 17–20 |
| 22 | Erweiterte Privacy-/Utility-Metriken | P1/P2 | 21 |
| 23 | Evaluation Framework und Benchmarks | P1 | 18–22 |
| 24 | Performanceoptimierung | P1 | 23 |
| 25 | Erweiterte Bewegung | P2 | Unabhängig |
| 26 | 3D-/erweiterter Renderer | P2 | Unabhängig |

---

# 19. Definition of Done

```text
1. Simulation generates ground-truth agent states.
2. Sensor receives current agent states.
3. Sensor model produces measurements.
4. Measurements are assigned to max-depth quadtree leaves.
5. Temporal storage retains the required measurement history.
6. AggregationManager evaluates candidate aggregations.
7. Regional policies are applied.
8. Privacy and utility constraints are evaluated.
9. Spatial and/or temporal aggregation is performed.
10. Invalid publication candidates are rejected.
11. Valid aggregated cells are released.
12. Sensor publishes the results.
13. Renderer visualizes the published cells.
14. Evaluation Framework records relevant metrics.
15. Results are reproducible and comparable with baselines.
```

**Unverzichtbare Invarianten:**

- Keine Veröffentlichung ohne erfüllte Constraints.
- Keine unbeabsichtigte doppelte Zählung von Messbeiträgen.
- Keine Veränderung der Ground Truth durch das Sensormodell.
- Keine Topologieänderung während der Aggregation.
- Keine unbegrenzte Historie.
- Keine unkontrollierte Herausgabe von Agentenidentitäten.

---

# 20. Direkt verwendbare Arbeitsanweisung an Codex

> **Projektauftrag:**
>
> Entwickle die bestehende C++17-basierte Urban-Mobility-Simulation zu einem modularen Framework für adaptive, policygesteuerte, räumlich-zeitliche Aggregation von Mobilitätsdaten weiter.
>
> Die wissenschaftliche Kerninnovation besteht in der Kombination aus einem intern maximal aufgelösten Quadtree, retrospektiver zeitlicher Aggregation, regional definierten Privacy- und Utility-Constraints sowie konfigurierbaren Aggregationsstrategien.
>
> **Vorgehen:** Analysiere zuerst den vorhandenen Code vollständig: Klassen, Abhängigkeiten, Datenstrukturen, Thread-Grenzen, Datenflüsse und aktuelle Funktionalität. Erstelle danach einen konkreten Refactoring- und Implementierungsplan, der möglichst viel Bestehendes erhält. Verwende diesen Aktionsplan als funktionale Spezifikation.
>
> Implementiere schrittweise und priorisiere Korrektheit, Modularität, Determinismus und Testbarkeit. Die Aggregation bleibt sensorlokal. Der Sensor verantwortet MongoDB und weitere Veröffentlichungen. Der AggregationManager besitzt keine Datenbankabhängigkeit.
>
> Der Quadtree besitzt nach Initialisierung statische Topologie. Räumliche Aggregation ändert ausschließlich die Veröffentlichungsansicht. Entwickle eine begrenzte In-Memory-Zeithistorie für retrospektive Parent-Aggregation. Unterscheide Messereignisse, eindeutige Agenten, aggregierte Datensätze und veröffentlichte Beiträge strikt.
>
> Sämtliche Privacy-/Utility-Constraints müssen anhand definierter Metriken prüfbar sein. Bestehende Simulation, Sensorhierarchie, Renderer und Datenbankkommunikation funktionsfähig halten. Multi-Sensor-Fusion, 3D-Rendering, komplexes Path Planning und UDS nicht als erste Schritte beginnen.
>
> **Nicht alles auf einmal implementieren.** Beginne ausschließlich mit **Phase 0: Bestandsaufnahme**. Dokumentiere Architekturentscheidungen, identifiziere konkrete Änderungen pro Datei und ergänze für jede neue Kernfunktion automatisierte Tests. Starte größere Refactorings erst auf Grundlage des auditierten Ist-Zustands.

---

## Abschließende technische Priorität

Der statische Quadtree ist nicht das größte Risiko. **Die richtige temporale Datenhaltung bei variabler räumlicher Aggregation ist der kritische Pfad.** Sie bestimmt, ob `spatial_first`, `temporal_first`, retrospektive Parents, Privacy-Checks, Data Fidelity und reproduzierbare Evaluation überhaupt konsistent zusammenarbeiten.

**Unmittelbarer nächster Schritt für Codex:** Phase 0 durchführen und die tatsächliche Zielarchitektur auf Grundlage des vorliegenden Repository-Codes erstellen. Noch keine großflächigen Änderungen.
