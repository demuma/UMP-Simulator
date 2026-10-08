# UrbanMobilityPrivacy

Lokale Forschungsbasis für räumlich-zeitliche Aggregation urbaner Mobilitätsdaten.

## Herkunft und Stand

Import am 2026-10-08 aus dem lokalen Repository Coding, Commit `d1e3dde748c6565ca4a44514d5e9e86016b67de3`.
`simulator/` stammt aus `Aggregation_Manager`; `renderers/{abs,gbs,agbs,gt}`
aus den jeweiligen V3-Datenbank-Renderern. Quellcode und YAML-Konfigurationen
wurden unverändert übernommen. Bestehende Projekte bleiben erhalten.
Noch keine gemeinsame Bibliothek, kein neuer Aggregationsalgorithmus und kein Remote.
Nach dem Import wurden die ABS-Geschwindigkeitsschätzung und die einmalige Batch-Ausgabe
korrigiert; der ursprüngliche Import ist im ersten Commit erhalten.

Der importierte Plan unter `docs/reference/` ist eine historische Referenz,
keine verbindliche Arbeitsanweisung. Die aktuelle Bewertung steht in
[docs/STATE_AND_NEXT_STEPS.md](docs/STATE_AND_NEXT_STEPS.md).

## Build

Abhängigkeiten: C++17, CMake, SFML 3, yaml-cpp, MongoDB-C++-Treiber (mongocxx/bsoncxx).
Die übernommenen CMake-Dateien enthalten noch lokale Homebrew-Pfade.

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j4
cmake -S renderers/abs -B renderers/abs/build -DCMAKE_BUILD_TYPE=Release
cmake --build renderers/abs/build -j4
```

Die weiteren Renderer analog einzeln bauen. Sie besitzen jeweils denselben
Targetnamen `Visualizer`; eine gemeinsame CMake-Struktur folgt bei Bedarf.
Zum Starten jeweils das Komponentenverzeichnis als Arbeitsverzeichnis verwenden,
weil `config.yaml` relativ geladen wird.

## Laufzeitstatus

Simulator und alle vier Renderer wurden als Release-Build erfolgreich gebaut.
101 übernommene Dateien wurden byteweise mit den Originalen verglichen.
Noch keine Laufzeitvalidierung des Imports. Die Simulator-Konfiguration enthält
`clear_database: true`; ein unveränderter Start löscht die konfigurierten Collections.
Daher vor einem Lauf eine eigene Experimentdatenbank konfigurieren.
Headless deaktiviert momentan nur das Fenster, nicht Snapshot-Erzeugung oder Datenbank-I/O.
Schriftpfade sind noch macOS-spezifisch.

## Nächstes Experiment

Identischer Messstrom, feste räumliche Zellen und Zeitfenster; Vergleich einer
fest definierten Belegungsabfrage mit Ground Truth. Eine k-basierte Freigaberegel
wird von einer unabhängigen empirischen Angreiferbewertung getrennt.

## Regressionstests

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build simulator/build -j4
ctest --test-dir simulator/build --output-on-failure
```

Die ABS-Regressionstests verwenden synthetische Beobachtungen mit bekannten Geschwindigkeiten
und benötigen keine Datenbankverbindung oder ein Grafikfenster.
