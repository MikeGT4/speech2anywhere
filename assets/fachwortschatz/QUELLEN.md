# Quellen des Fachwortschatzes

- Quelle: Wikidata, https://www.wikidata.org, Abfragen über https://query.wikidata.org/sparql
- Lizenz: CC0 1.0, https://www.wikidata.org/wiki/Wikidata:Licensing
- Abrufdatum: 2026-11-18
- Erzeugt mit `scripts/build_fachwortschatz.py`

## Auswahl

- Begriffe: Bezeichnung (rdfs:label) und Kurzname (P1813) in der Sprache der Datei, ersatzweise die
  sprachübergreifende Bezeichnung (mul).
- Aliasse (skos:altLabel) stehen hinter allen Bezeichnungen. Hat ein Eintrag keine verwendbare Bezeichnung
  und ist diese kein Alltagswort, rücken bis zu 2 Aliasse an ihre Stelle. Kurznamen von
  Einträgen, deren Bezeichnung ein Alltagswort ist, stehen ebenfalls hinten.
- Aliasse entfallen, wenn sie der englischen Bezeichnung gleichen, die Bezeichnung nur erweitern oder beugen.
- Reihenfolge: Zahl der Sitelinks des Eintrags, bei Gleichstand alphabetisch; höchstens 3000 Begriffe
  je Datei.
- Form: 3 bis 60 Zeichen, höchstens 4 Wörter, lateinische und griechische Buchstaben,
  keine Klammern, Kommas oder ziffernlastigen Kennungen.
- Alltagswörter: Deutsch ohne die 20.000 häufigsten Wörter aus wordfreq (v3.2,
  https://github.com/rspeer/wordfreq, Daten CC BY-SA 4.0); die Liste dient nur als Filter, kein Wort daraus
  ist übernommen. Deutsche Aliasse zusätzlich ohne Einzelwörter aus `assets/wordlist-de.txt`. Übrige Sprachen
  ohne einzelne kleingeschriebene Wörter bis 6 Zeichen.
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
- Instanzen von Q2135465 Rechtsbegriff
- Instanzen von Q130583773 Art des Verbrechens
- Instanzen von Q131784846 type of contract
- Unterklassen von Q41487 Gericht
- Instanzen und Unterklassen von Q41487 Gericht; mindestens 10 Sitelinks
- Unterklassen von Q158970 Delikt
- Unterklassen von Q689247 Rechtsmittel
- Unterklassen von Q697327 Klage
- Unterklassen von Q1301203 Prozess
- Instanzen und Unterklassen von Q1938208 Rechtsinstitut
- Instanzen und Unterklassen von Q3237872 Grundrecht
- Unterklassen von Q8458 Menschenrechte
- Instanzen und Unterklassen von Q10353985 legal principle
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q183 Deutschland; nur für de
- Einträge mit P9696 Buzer.de-Gesetzeskennung; nur für de
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q145 Vereinigtes Königreich, Q30 Vereinigte Staaten; nur für en
- Einträge mit P3343 legislation.gov.uk-ID; nur für en
- Einträge mit P3837 Öffentliches Recht der Vereinigten Staaten; nur für en
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q142 Frankreich; nur für fr
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q38 Italien; nur für it
- Einträge mit P8722 Normattiva ID; nur für it
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q55 Niederlande; nur für nl
- Einträge mit P13979 BWB-Nummer; nur für nl
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q36 Polen; nur für pl
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q45 Portugal, Q155 Brasilien; nur für pt
- Einträge mit P9119 LexML Brazil ID; nur für pt
- Instanzen von den Gesetzesklassen; Geltungsbereich oder Staat Q29 Spanien; nur für es
- Einträge mit P4256 BOE-Kennung; nur für es

### wirtschaft

- Einträge mit P10715 Investopedia-Begriffskennung; ohne Instanzen von Q5 Mensch und deren Unterklassen; ohne P856, P159, P625
- Instanzen und Unterklassen von Q29028649 wirtschaftliches Konzept
- Unterklassen von Q247506 Finanzinstrument; ohne P498
- Instanzen und Unterklassen von Q832161 betriebswirtschaftliche Kennzahl
- Instanzen und Unterklassen von Q1167393 ökonomische Kennzahl
- Unterklassen von Q8161 Steuer
- Instanzen von Q130109687 Steuerart
- Unterklassen von Q273005 Wirtschaftssystem; ohne Instanzen von Q14827288 Wikimedia-Projekt und deren Unterklassen
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

### technik

- Instanzen und Unterklassen von Q107715 physikalische Größe; nur mit P416, P2534, P4020, P8855
- Instanzen und Unterklassen von Q47574 Maßeinheit; nur mit P2370, P7825, P2968; ohne P498
- Einträge mit P7825 UCUM-Code
- Instanzen und Unterklassen von Q214070 physikalisches Gesetz
- Unterklassen bis zur zweiten Ebene von Q1293220 physikalisches Phänomen
- Instanzen von Q125517960 type of electronic component
- Unterklassen von Q11653 elektronisches Bauelement
- Einträge mit P8855 IEV-Nummer
- Unterklassen bis zur zweiten Ebene von Q839546 Maschinenelement
- Unterklassen von Q2041172 Messgerät
- Instanzen und Unterklassen von Q1408288 Fertigungsverfahren
- Instanzen von Q4162444 Teilgebiet der Physik
- Unterklassen von Q11023 Ingenieurwissenschaft
- Unterklassen bis zur zweiten Ebene von Q44167 Motor
- Instanzen von Q173227 physikalische Konstante
- Instanzen von Q140424281 type of device

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

Gesetzesklassen: Q820655 Gesetz, Q922203 Gesetzbuch, Q1923776 Zivilgesetzbuch, Q7755 Verfassung, Q2076487 organic law, Q6453643 decree-law, Q2703920 Verordnung, Q3042975 Real Decreto (Spanien), Q13408009 französisches Gesetz, Q4677783 Act of Parliament (Großbritannien), Q1006079 Bundesgesetz (Deutschland), Q16603799 Bundesverordnung (Deutschland).

Eigenschaften in den Filtern: P159 Hauptverwaltung, P225 wissenschaftlicher Name, P267 ATC-Code, P416 Formelzeichen (string), P486 MeSH-Kennung, P493 ICD-9, P494 ICD-10 Identifikator, P498 Währungscode (ISO 4217), P557 DiseasesDB-ID, P604 MedlinePlus-Kennung, P625 geographische Koordinaten, P673 eMedicine, P699 Disease-Ontology-ID, P715 Drugbank-ID, P856 offizielle Website, P1323 Terminologia-Anatomica-98-ID, P1402 Foundational-Model-of-Anatomy-Kennung, P1690 ICD-10-PCS, P1692 ICD-9-CM, P2370 Umrechnung in SI-Einheit, P2534 Formel, P2968 QUDT Maßeinheiten-Kennung, P4020 Dimension gemäß Internationalem Größensystem, P4338 LOINC-Kennung, P5806 SNOMED-CT-ID, P7807 ICD-11 Identifikator (Foundation), P7825 UCUM-Code, P8855 IEV-Nummer.

## Begriffe je Datei

| Gebiet | de | en | fr | it | nl | pl | pt | es |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| medizin | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
| medikamente | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
| jura | 3000 | 3000 | 2186 | 1280 | 1726 | 964 | 1192 | 2166 |
| wirtschaft | 3000 | 3000 | 3000 | 2179 | 2420 | 1936 | 1927 | 3000 |
| technik | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
| chemie | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
| it | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 | 3000 |
