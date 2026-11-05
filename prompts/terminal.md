Du bekommst einen per Spracherkennung transkribierten Text, der in einem Terminal-Fenster landet.

Regeln:
- Wenn der Text wie Konversation klingt (vollständiger Satz, Pronomen, Fragepartikel): gib ihn fast unverändert zurück. Entferne nur die Satzschluss-Punktuation (Komma, Punkt) und die deutsche Anführungszeichen. Änderungen sonst minimal.
- Wenn der Text wie ein Shell-Kommando klingt (kurz, Verb-am-Anfang wie `cd`, `ls`, `git`, `docker`, `ssh`, mit Flags/Pfaden): korrigiere offensichtliche Transkriptionsfehler in den Kommando-Tokens.
- NIE Beispiele oder Default-Texte einfügen. Wenn unklar: einfach den Input fast wörtlich zurückgeben.

Beispiele (NICHT als Output-Vorlage verwenden, nur als Illustration):
- Konversation "Mach mal git pull bitte" -> "Mach mal git pull bitte"
- Konversation "Schau mal in den Logs nach" -> "Schau mal in den Logs nach"
- Kommando "get status" -> "git status"
- Kommando "ssh root att 192 0 2 10" -> "ssh root@192.0.2.10"

Gib NUR den polierten Text zurück: kein Kommentar, keine Erklärung, kein Beispiel.

Input:
{text}

Output:
