# Quellen des Fachwortschatzes

- Quelle: Wikidata, https://www.wikidata.org, Abfragen über https://query.wikidata.org/sparql
- Lizenz: CC0 1.0, https://www.wikidata.org/wiki/Wikidata:Licensing
- Abrufdatum: 2026-11-19
- Erzeugt mit `scripts/build_fachwortschatz.py`

## Auswahl

- Begriffe: Bezeichnung (rdfs:label) und Kurzname (P1813) in der Sprache der Datei, ersatzweise die
  sprachübergreifende Bezeichnung (mul). Stereodeskriptoren am Anfang wie „(RS)-“ oder „(±)-“ entfallen.
- Die Oberklassen der Abfragen nach Unterklassen zählen selbst als Einträge.
- Fachsynonyme: bis zu 2 Aliasse (skos:altLabel) je Eintrag stehen direkt bei der Bezeichnung, außer bei
  Einträgen, deren Bezeichnung ein Einzelwort ab Zipf 4,0 ist,
  wenn sie der Bezeichnung desselben Eintrags in einer anderen Sprache ähneln (Ähnlichkeit ab
  0,8 nach Angleichung der Schreibung ä/ae, ö/oe, ü/ue, ph/f, th/t, rh/r, ae/oe/e, qu/k/z/c, y/i),
  mindestens 7 Buchstaben und keine Ziffern haben, nur Buchstaben der Sprache der Datei enthalten
  und jedes ihrer Wörter in den wordfreq-Daten dieser Sprache vorkommt. Schreibvarianten der Bezeichnung
  (Ähnlichkeit ab 0,9) und seltenere Ableitungen von ihr (gemeinsamer Wortanfang über
  mindestens 0,75 des kürzeren Begriffs) zählen nicht; von mehreren Schreibvarianten bleibt
  die in wordfreq häufigere.
- Übrige Aliasse stehen hinter allen Bezeichnungen. Hat ein Eintrag keine verwendbare Bezeichnung
  und ist diese kein Alltagswort, rücken bis zu 2 Aliasse an ihre Stelle. Kurznamen von
  Einträgen, deren Bezeichnung ein Alltagswort ist, stehen ebenfalls hinten.
- Aliasse entfallen, wenn sie Buchstabe für Buchstabe einem englischen Begriff des Eintrags gleichen, die
  Bezeichnung nur erweitern oder beugen.
- Reihenfolge: Zahl der Sitelinks des Eintrags, bei Gleichstand alphabetisch; findet nur eine Abfrage mit
  Gewichtsfaktor den Eintrag, zählen seine Sitelinks mit diesem Faktor. Höchstens so viele Begriffe je
  Datei: medizin 6.000, medikamente 5.000, chemie 5.000, sonst 3.000.
- Form: 3 bis 60 Zeichen, höchstens 4 Wörter, lateinische und griechische Buchstaben,
  keine Klammern, Kommas oder ziffernlastigen Kennungen.
- Alltagswörter (wordfreq v3.2, https://github.com/rspeer/wordfreq, Daten CC BY-SA 4.0): Deutsch ohne
  die 20.000 häufigsten Wörter, außer Wörtern mit Großbuchstaben im Wortinneren; übrige
  Sprachen ohne kleingeschriebene Einzelwörter ab Zipf 4,0 und großgeschriebene ab Zipf 5,0. Die Häufigkeiten dienen nur als
  Filter und zur Wahl zwischen Schreibvarianten, kein Wort daraus ist übernommen. Deutsche Aliasse zusätzlich
  ohne Einzelwörter aus `assets/wordlist-de.txt`.
- Ergänzung: gängige Fachbegriffe aus `scripts/fachbegriffe_ergaenzung.json` (eigene Liste) stehen am Anfang
  ihrer Datei, soweit die Abfragen sie nicht liefern.
- Ausgeschlossen: Instanzen von Q115305900 großes Sprachmodell, Q870780 Chatbot. Einzeln ausgeschlossen, weil ihre Bezeichnungen mit
  Produkt- oder Personennamen zusammenfallen: Q248542, Q1126839, Q1977520, Q25110971, Q94638515, Q134083964, Q136549314.

## Klassen je Fachgebiet

### medizin

- Instanzen von Q112193867 Krankheitstyp
- Instanzen von Q12136 Krankheit
- Unterklassen von Q12136 Krankheit; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Instanzen von Q130753312 Symptomtyp
- Unterklassen von Q1441305 klinisches Zeichen; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Instanzen und Unterklassen von Q169872 Symptom; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Instanzen von Q112826905 Klasse anatomischer Entitäten; nur mit P1402, P1323
- Instanzen von Q103812529 Organtyp; nur mit P1402, P1323
- Unterklassen von Q4936952 anatomische Struktur; nur mit P1402, P1323
- Instanzen von Q55215251 Art von medizinischer Test
- Instanzen und Unterklassen von Q2671652 medizinische Untersuchung; nur mit P1692, P1690, P5806, P4338
- Instanzen und Unterklassen von Q796194 medizinisches Verfahren; nur mit P1692, P1690, P5806, P4338
- Instanzen und Unterklassen von Q15636229 chirurgischer Eingriff; nur mit P1692, P1690, P5806, P4338
- Instanzen und Unterklassen von Q930752 medizinisches Fachgebiet
- Instanzen und Unterklassen von Q12135 psychische Störung; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Instanzen und Unterklassen von Q193078 Trauma; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Instanzen und Unterklassen von Q179630 Syndrom; nur mit P494, P7807, P493, P699, P486, P604, P557, P673, P5806
- Einträge mit P672 MeSH-Code (Wert beginnt mit A01, A02, A03, A04, A05, A06, A07, A08, A09, A10, A11, A12, A14, A15, A16, A17, C, E01, E02, E03, E04, E06, F03, H02.403); ohne Werte ab E01.370.350.600, E02.190.901, F03.250.400

### medikamente

- Einträge mit P267 ATC-Code; ohne Werte ab V01, V03AN, V07; ohne Instanzen von Q11344 chemisches Element und deren Unterklassen
- Instanzen von Q2585617 Wirkstoffklasse
- Instanzen und Unterklassen von Q12140 Arzneimittel; nur mit P267, P715; ohne Instanzen von Q11344 chemisches Element und deren Unterklassen
- Instanzen und Unterklassen von Q134808 Impfstoff
- Einträge mit P672 MeSH-Code (Wert beginnt mit D27.505)
- Instanzen von Q28885102 pharmazeutisches Produkt; auch ohne Sitelinks

### jura

- Instanzen von Q1756157 Rechtszweig
- Instanzen von Q2135465 Rechtsbegriff; ohne Unterklassen bis zur dritten Ebene von Q43229 Organisation
- Instanzen von Q130583773 Art des Verbrechens
- Instanzen von Q131784846 type of contract
- Unterklassen von Q41487 Gericht
- Instanzen und Unterklassen von Q1262438 internationales Gericht; ohne P576
- Unterklassen von Q158970 Delikt
- Unterklassen von Q689247 Rechtsmittel
- Unterklassen von Q697327 Klage
- Unterklassen von Q1301203 Prozess; ohne P580, P582, P585
- Instanzen und Unterklassen von Q1938208 Rechtsinstitut
- Instanzen und Unterklassen von Q3237872 Grundrecht
- Unterklassen von Q8458 Menschenrechte
- Instanzen und Unterklassen von Q10353985 legal principle
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q183 Deutschland; ohne P576, P582; nur für de
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q183 Deutschland; ohne P576; mindestens 5 Sitelinks; nur für de
- Einträge mit P9696 Buzer.de-Gesetzeskennung; nur für de
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q145 Vereinigtes Königreich, Q30 Vereinigte Staaten; ohne P576, P582; nur für en
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q145 Vereinigtes Königreich, Q30 Vereinigte Staaten; ohne P576; mindestens 5 Sitelinks; nur für en
- Einträge mit P3343 legislation.gov.uk-ID; nur für en
- Einträge mit P3837 Öffentliches Recht der Vereinigten Staaten; nur für en
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q142 Frankreich; ohne P576, P582; nur für fr
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q142 Frankreich; ohne P576; mindestens 5 Sitelinks; nur für fr
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q38 Italien; ohne P576, P582; nur für it
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q38 Italien; ohne P576; mindestens 5 Sitelinks; nur für it
- Einträge mit P8722 Normattiva ID; nur für it
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q55 Niederlande; ohne P576, P582; nur für nl
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q55 Niederlande; ohne P576; mindestens 5 Sitelinks; nur für nl
- Einträge mit P13979 BWB-Nummer; nur für nl
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q36 Polen; ohne P576, P582; nur für pl
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q36 Polen; ohne P576; mindestens 5 Sitelinks; nur für pl
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q45 Portugal, Q155 Brasilien; ohne P576, P582; nur für pt
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q45 Portugal, Q155 Brasilien; ohne P576; mindestens 5 Sitelinks; nur für pt
- Einträge mit P9119 LexML Brazil ID; nur für pt
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q29 Spanien; ohne P576, P582; nur für es
- Instanzen und Unterklassen von Q41487 Gericht; Geltungsbereich oder Staat Q29 Spanien; ohne P576; mindestens 5 Sitelinks; nur für es
- Einträge mit P4256 BOE-Kennung; nur für es

### wirtschaft

- Einträge mit P10715 Investopedia-Begriffskennung; ohne Instanzen von Q5 Mensch und deren Unterklassen; ohne Unterklassen bis zur dritten Ebene von Q43229 Organisation; ohne P856, P159, P625, P571, P576, P580, P582, P585; Sitelinks zählen mit dem Faktor 0,25
- Instanzen und Unterklassen von Q29028649 wirtschaftliches Konzept
- Unterklassen von Q247506 Finanzinstrument; ohne direkte Instanzen und Unterklassen von Q1368 Geld, Q8142 Währung, Q41207 Münze, Q113813711 Münzart; ohne P498
- Instanzen und Unterklassen von Q832161 betriebswirtschaftliche Kennzahl
- Instanzen und Unterklassen von Q1167393 ökonomische Kennzahl
- Unterklassen von Q8161 Steuer
- Instanzen von Q130109687 Steuerart
- Unterklassen von Q273005 Wirtschaftssystem; ohne Instanzen von Q14827288 Wikimedia-Projekt und deren Unterklassen; ohne direkte Instanzen und Unterklassen von Q10876391 Wikipedia-Sprachauflage
- Unterklassen von Q815823 Geschäftsmodell
- Instanzen von Q1269299 Rechtsform für Unternehmen
- Unterklassen von Q192907 Jahresabschluss
- Unterklassen von Q169489 Wertpapier
- Unterklassen von Q43183 Versicherung
- Unterklassen von Q22687 Bank
- Unterklassen von Q189539 Darlehen
- Instanzen und Unterklassen von Q1779838 Rechnungslegungsstandard
- Instanzen und Unterklassen von Q3048444 Schule der Wirtschaftstheorie
- Instanzen und Unterklassen von Q1401304 Wirtschaftstheorie
- Unterklassen von Q208697 Finanzmarkt
- Unterklassen von Q39809 Vermarktung
- Unterklassen von Q2851421 costs
- Unterklassen von Q4116214 Buchhaltung
- Instanzen von Q64588497 accounting term
- Instanzen von Q116460050 Eigentumstyp
- Instanzen von Q106905561 Bilanzkennzahl
- Instanzen von Q64513545 Wirtschaftsterminologie
- Unterklassen von Q8137 Kapital
- Unterklassen von Q170924 Zins
- Unterklassen von Q1527264 Einkommen
- Unterklassen von Q1166072 Transaktion
- Unterklassen von Q160151 Preis

### technik

- Instanzen und Unterklassen von Q107715 physikalische Größe; nur mit P416, P2534, P4020, P8855
- Instanzen und Unterklassen von Q47574 Maßeinheit; nur mit P2370, P7825, P2968; ohne P498
- Einträge mit P7825 UCUM-Code
- Instanzen und Unterklassen von Q214070 physikalisches Gesetz
- Unterklassen bis zur zweiten Ebene von Q1293220 physikalisches Phänomen
- Instanzen von Q125517960 type of electronic component
- Unterklassen von Q11653 elektronisches Bauelement
- Einträge mit P8855 IEV-Nummer; ohne direkte Instanzen und Unterklassen von Q112193867 Krankheitstyp, Q1441305 klinisches Zeichen, Q2996394 biologischer Vorgang; ohne P686
- Unterklassen bis zur zweiten Ebene von Q839546 Maschinenelement
- Unterklassen von Q2041172 Messgerät
- Instanzen und Unterklassen von Q1408288 Fertigungsverfahren
- Instanzen von Q4162444 Teilgebiet der Physik
- Unterklassen von Q11023 Ingenieurwissenschaft
- Unterklassen bis zur zweiten Ebene von Q44167 Motor
- Instanzen von Q173227 physikalische Konstante
- Instanzen von Q140424281 type of device
- Instanzen von Q137582043 Teilgebiet der Mechanik
- Unterklassen von Q1480529 Fügen

### chemie

- Instanzen von Q11344 chemisches Element
- Einträge mit P231 CAS-Nummer; ohne P225; mindestens 3 Sitelinks
- Instanzen und Unterklassen von Q36534 chemische Reaktion
- Instanzen und Unterklassen von Q44424 chemische Bindung
- Instanzen und Unterklassen von Q170409 funktionelle Gruppe
- Instanzen von Q11790203 Teilgebiet der Chemie
- Unterklassen von Q834028 Laborgerät
- Instanzen und Unterklassen von Q898987 Trennverfahren
- Instanzen und Unterklassen von Q2281940 chemischer Prozess
- Instanzen und Unterklassen von Q764285 Stoffeigenschaft
- Instanzen von Q55640599 Gruppe chemischer Einheiten
- Unterklassen bis zur zweiten Ebene von Q81163 Polymer
- Unterklassen von Q37756 Legierung
- Instanzen von Q47154513 Strukturklasse von chemischen Verbindungen
- Instanzen von Q56256173 Klasse von chemischen Verbindungen mit ähnlichen Anwendungen oder Funktionen
- Instanzen von Q4751159 chemisches Analyseverfahren
- Instanzen von Q3247516 Labormethode
- Unterklassen von Q71550700 chemische Größe

### it

- Instanzen und Unterklassen von Q9143 Programmiersprache
- Instanzen und Unterklassen von Q9135 Betriebssystem
- Instanzen und Unterklassen von Q6368 Webbrowser
- Instanzen und Unterklassen von Q235557 Dateiformat
- Instanzen und Unterklassen von Q15836568 Netzwerkprotokoll
- Instanzen und Unterklassen von Q132364 Kommunikationsprotokoll
- Instanzen und Unterklassen von Q188860 Programmbibliothek
- Instanzen und Unterklassen von Q271680 Framework
- Instanzen und Unterklassen von Q1330336 Webframework
- Instanzen und Unterklassen von Q175263 Datenstruktur
- Instanzen und Unterklassen von Q8366 Algorithmus
- Instanzen und Unterklassen von Q188267 Programmierparadigma
- Instanzen und Unterklassen von Q37045 Auszeichnungssprache
- Instanzen und Unterklassen von Q845739 Abfragesprache
- Instanzen und Unterklassen von Q174989 Dateisystem
- Instanzen und Unterklassen von Q13741 IDE
- Instanzen und Unterklassen von Q131212 Texteditor
- Instanzen und Unterklassen von Q3257930 Versionsverwaltungssystem
- Instanzen und Unterklassen von Q176165 Datenbankmanagementsystem
- Instanzen von Q17155032 Software-Typ
- Instanzen von Q66747126 Begriff aus den Computerwissenschaften
- Instanzen und Unterklassen von Q14001 Schadprogramm
- Unterklassen von Q3966 Hardware
- Instanzen und Unterklassen von Q181156 Softwareentwurfsmuster
- Unterklassen von Q4071928 Cyberattacke
- Instanzen und Unterklassen von Q11288 Webserver
- Instanzen und Unterklassen von Q11189 Proxy
- Instanzen und Unterklassen von Q71550 Anwendungsserver
- Instanzen und Unterklassen von Q7935198 Virtualisierungslösung
- Instanzen und Unterklassen von Q118218718 container orchestrator
- Instanzen und Unterklassen von Q1077480 Hypervisor
- Instanzen und Unterklassen von Q16947796 kontinuierliche Integrationssoftware
- Instanzen und Unterklassen von Q29032804 configuration manager
- Instanzen und Unterklassen von Q138081337 infrastructure provisioning tool
- Instanzen und Unterklassen von Q13224353 Monitoring-Software
- Instanzen und Unterklassen von Q1480561 Issue-Tracking-System
- Instanzen und Unterklassen von Q141089604 VPN software
- Instanzen und Unterklassen von Q91348108 daemon-managing daemon
- Instanzen und Unterklassen von Q1092177 Message Oriented Middleware
- Instanzen und Unterklassen von Q756230 Verzeichnisdienst
- Instanzen und Unterklassen von Q14663 Unix-Shell
- Instanzen und Unterklassen von Q891055 Paketverwaltung
- Instanzen und Unterklassen von Q2727468 Build-Automatisierung
- Instanzen und Unterklassen von Q47506 Compiler

Gesetzesklassen: Q820655 Gesetz, Q922203 Gesetzbuch, Q1923776 Zivilgesetzbuch, Q7755 Verfassung, Q2076487 organic law, Q6453643 decree-law, Q2703920 Verordnung, Q3042975 Real Decreto (Spanien), Q13408009 französisches Gesetz, Q4677783 Act of Parliament (Großbritannien), Q1006079 Bundesgesetz (Deutschland), Q16603799 Bundesverordnung (Deutschland).

Eigenschaften in den Filtern: P159 Hauptverwaltung, P225 wissenschaftlicher Name, P267 ATC-Code, P416 Formelzeichen (string), P486 MeSH-Kennung, P493 ICD-9, P494 ICD-10 Identifikator, P498 Währungscode (ISO 4217), P557 DiseasesDB-ID, P571 Datum der Gründung, Entstehung, Erbauung, P576 Auflösungsdatum, P580 Startzeitpunkt, P582 Endzeitpunkt, P585 Zeitpunkt/Stand, P604 MedlinePlus-Kennung, P625 geographische Koordinaten, P673 eMedicine, P686 Gene-Ontology-Identifikator, P699 Disease-Ontology-ID, P715 Drugbank-ID, P856 offizielle Website, P1323 Terminologia-Anatomica-98-ID, P1402 Foundational-Model-of-Anatomy-Kennung, P1690 ICD-10-PCS, P1692 ICD-9-CM, P2370 Umrechnung in SI-Einheit, P2534 Formel, P2968 QUDT Maßeinheiten-Kennung, P4020 Dimension gemäß Internationalem Größensystem, P4338 LOINC-Kennung, P5806 SNOMED-CT-ID, P7807 ICD-11 Identifikator (Foundation), P7825 UCUM-Code, P8855 IEV-Nummer.

## Begriffe je Datei

| Gebiet | de | en | fr | it | nl | pl | pt | es |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| medizin | 6000 | 6000 | 6000 | 6000 | 6000 | 6000 | 6000 | 6000 |
| medikamente | 4411 | 5000 | 4094 | 3297 | 3035 | 3275 | 4203 | 4082 |
| jura | 3000 | 3000 | 1986 | 1135 | 1620 | 873 | 1077 | 1961 |
| wirtschaft | 3000 | 3000 | 3000 | 1971 | 2388 | 1721 | 1901 | 3000 |
| technik | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
| chemie | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 |
| it | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
