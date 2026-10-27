# Changelog

## 0.5.10 (27.10.2026)

- Sicherheit beim Update: Die App prüft die Verbindung zu GitHub gegen ihre eigene Zertifikatsliste statt gegen die von Windows und vertraut der Wurzel „emSign ECC Root CA - G3“ nicht mehr, unter der eMudhra Zwischenzertifikate mit erratbaren Schlüsseln ausgegeben hat
- Von 0.5.5 bis 0.5.9 aus lädt das Update in der App nur das Programmpaket (rund 1,5 MB)

## 0.5.9 (26.10.2026)

- Anzeige im Stil Comic: Sind die „Wortfetzen“ an, liegen beim Polieren die ersten Wörter deines Diktats auf dem Bogen unter dem Bügeleisen statt „Bla bla blubb, bla bla!“
- Von 0.5.5 bis 0.5.8 aus lädt das Update in der App nur das Programmpaket (rund 1,5 MB)

## 0.5.8 (23.10.2026)

- Menü am Tray-Symbol: Steht die Maus über einem Punkt, wird sein rundes Symbol hell und hebt sich von der gelben Pille ab; der unterste Punkt „Beenden“ bleibt dabei im Rahmen
- Von 0.5.5, 0.5.6 und 0.5.7 aus lädt das Update in der App nur das Programmpaket (rund 1,5 MB)

## 0.5.7 (23.10.2026)

- Das Menü am Tray-Symbol im verspielten Comic-Stil: vor jedem Punkt ein rundes gelbes Symbol, der gewählte Punkt als gelbe Pille, oben eine Statuskarte mit dem Gesicht der Sprechblase, cremefarbene Fläche mit runden Ecken und gepunktete Trenner
- Von 0.5.5 und 0.5.6 aus lädt das Update in der App nur das Programmpaket (rund 1,5 MB)

## 0.5.6 (22.10.2026)

- Zwei neue Anzeige-Stile für die Saison, wählbar in den Einstellungen unter „Anzeige“: „Halloween (Hexenhut)“ mit Hexenhut, leuchtendem Kürbis im Hintergrund, Hexenkessel, Besen, Kürbisschnitzen und einem Mond als Uhr; „Weihnachten (Winternacht)“ mit Nikolausmütze und Bart in einer verschneiten Winternacht, Schlitten, Lichterbogen, Plätzchen und einem Adventskranz als Uhr
- Die Wortfetzen fliegen auch in beiden neuen Stilen; der Schalter „Wortfetzen“ gilt für Comic, Manga, Halloween und Weihnachten
- Ladeanzeigen beim Laden der Modelle (Ersteinrichtung, Einstellungen, Ollama-Empfehlung), beim Download des Ollama-Setups und beim Voll-Update: Prozent, „x,x von y,y GB“, Tempo und Restzeit; solange noch keine Bytes messbar sind (Whisper über Xet), Größe und Laufzeit mit laufendem Balken
- „Datei transkribieren“ zeigt, ob gerade die Spracherkennung geladen oder die Datei gelesen wird, danach den Fortschritt nach Audiozeit mit Restzeit; „Abbrechen“ hält beim nächsten Abschnitt an
- Die Willkommensseite nach einem Update nennt oben, was neu ist
- Von 0.5.5 aus lädt das Update in der App nur das Programmpaket (rund 1,4 MB) statt des ganzen Pakets

## 0.5.5 (20.10.2026)

- Kleine Updates: Hat sich seit deiner Version nur das Programm geändert, lädt Speech2Anywhere statt des ganzen Pakets (rund 3 GB) nur das Programmpaket (gut 1 MB), prüft die Prüfsumme, spielt es ein und startet von selbst neu. Das greift ab dem ersten Update nach 0.5.5
- Empfehlung zu Ollama: Jedes Release nennt die Ollama-Version und die Fassungen der Politur-Modelle, mit denen es gemessen ist. Ist dein Ollama älter als das geprüfte oder nutzt du eines der gemessenen Modelle in einer anderen Fassung, meldet Speech2Anywhere das einmal im Tray. Das Windows-Ollama und das Modell aktualisierst du dort per Knopf, nie automatisch
- Das Setup bringt Ollama 0.40.5 mit (vorher 0.32.15). Ein schon installiertes Ollama bleibt unangetastet; die Empfehlung aktualisiert es auf Knopfdruck mit genau diesem Setup, ohne neuen Download
- Einstellungen, Reiter „Anzeige“: Eine bewegte Vorschau spielt ein Diktat im gewählten Stil ab, mit Aufnahme, Erkennen, Politur und „Zack!“
- Comic-Anzeige: Oben rechts läuft je Diktat ein Wecker, ein Zeitring oder eine Sanduhr mit
- Comic-Anzeige: In den fliegenden Wörtern steht wieder ein „l“, vorher sah „bla“ wie „b!a“ aus
- Das Update aus der App startet das Setup wieder. Seit 0.4.1 endete es nach dem Download mit „Abgebrochen.“; für den Schritt auf 0.5.5 bitte das Setup einmal von Hand starten. Wer das Update in der App schon versucht hat, findet das geladene Setup unter `%LOCALAPPDATA%\Kira\update\v0.5.5`. Speech2Anywhere vorher im Tray beenden, sonst beendet das Setup es selbst
- Das Setup spielt das eingebettete Python bei jedem Update frisch ein, mit genau den Bibliotheksfassungen des Release
- „Datei transkribieren“ meldet wieder, wo das Transkript liegt, und überschreibt keine vorhandene Textdatei mehr; „Abbrechen“ beim Laden eines Modells wirkt wieder

## 0.5.4 (19.10.2026)

- Neuer Anzeige-Stil „Manga“: weiße Comic-Tafel mit Fokuslinien und Rasterpunkten; ein kleiner Kung-Fu-Kämpfer schlägt die erkannten Wörter als Lettering ins Bild, sitzt beim Erkennen und bei der Politur im Lotussitz, springt beim „ZACK!“ und geht bei einem Fehler k.o. Wählbar in den Einstellungen unter „Anzeige“
- Die Bügel-Szene der Comic-Anzeige zeigt einen zerknitterten Zettel mit Text, der Bahn für Bahn glatt und weiß wird; das Bügeleisen hat eine Stahlsohle und dampft
- Zwei Schriften für die Manga-Anzeige liegen bei (Bangers und eine Katakana-Teilmenge der Dela Gothic One, beide OFL-Lizenz)

## 0.5.3 (02.10.2026)

- Beim Sprechen fliegen in der Comic-Anzeige Fetzen der erkannten Wörter aus dem Mund, in warmen Gelb- und Orangetönen; bis die ersten Wörter da sind, kommt „bla, bla, blubb!“. Abschaltbar in den Einstellungen unter „Anzeige“, Schalter „Wortfetzen“
- Die Denkwolke beim Erkennen und bei der Politur ist hellgelb statt weiß
- „ZU NAH!“ steht auf rotem Grund

## 0.5.2 (02.10.2026)

- Neue Denk-Animation in der Comic-Anzeige: je Diktat Waschtrommel, Bügeleisen oder Zahnräder; bei langem Warten wechselt die Szene frühestens nach 5 Sekunden, ab 6 Sekunden schwitzt das Maskottchen
- Um die Aufnahme-Anzeige liegt ab dem zweiten Diktat kein Fensterrand mehr
- Der Zwischenspeicher des Grafiktreibers (`CUDA_CACHE_MAXSIZE`) wird auf 4 GB gesetzt, damit das erste Diktat nach dem Hochfahren schneller ist

## 0.5.1 (01.10.2026)

- Ein kurzes „Danke“ oder „Vielen Dank“ bleibt erhalten, wenn es deutlich gesprochen wurde; verworfen wird es nur bei Stille oder Geräusch
- Das Tray-Menü öffnet sofort, auch wenn die App gerade beschäftigt ist
- Das Tray-Symbol schreibt während der Aufnahme keine temporären Dateien mehr
- Die Aufnahme-Anzeige zeichnet sparsamer

## 0.5.0 (30.09.2026)

- Neuer Name Speech2Anywhere, neues Logo, alle Fenster im Comic-Stil
- Neue Aufnahme-Anzeige als Standard, das Logo im Tray plappert während der Aufnahme
- Diktat-Taste F8 oder F9; ein unbekannter Wert aus einer älteren Einstellung startet mit F8
- Der Regler für die Verstärkung springt nicht mehr, Werte über 5,0 bleiben erhalten
- „Gelernte Wörter“ und „Über“ passen auf kleinere Bildschirme
- Die GPU-Prüfung nennt das Urteil zuerst
- Das digitalroots-Logo führt auf die Webseite
- Echte Umlaute in Installer, Assistent und Meldungen

Einstellungen und gelernte Wörter bleiben erhalten. Bis Version 0.4.3 hieß die App Kira.
