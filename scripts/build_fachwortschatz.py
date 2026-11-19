# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import argparse
import datetime
import difflib
import gzip
import hashlib
import http.client
import itertools
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "fachwortschatz-build/1.1 (https://speech2anywhere.de)"
LICENSE_URL = "https://www.wikidata.org/wiki/Wikidata:Licensing"
WORDFREQ_RELEASE = "v3.2"
WORDFREQ_COMMIT = "42233e6c36ce792031bcccfa17cdd0cec9af5fa7"
WORDFREQ_URL = "https://raw.githubusercontent.com/rspeer/wordfreq/{commit}/wordfreq/data/large_{language}.msgpack.gz"
WORDFREQ_SHA256 = {
    "de": "8ef04d3f4a28fb48d800d25fa80a96d90a5f80c8496c9a453f99f887c6ad3c12",
    "en": "dffae8066b78dce0a6667cf5f58e567054f902674667090a7ac8a8a44628b05c",
    "fr": "6f16cd80b9b66c5698ed002becea83ae30d0584c3205f1cf01714ad562c00c8b",
    "it": "0b5500e425a50e0f1fefb256d9125e74f586ac6b2f2a6e41bc96634bd5613cc7",
    "nl": "cfdae01b2ccd5bc94be046645b6ba8682e65d6709beedf6ab98d7bdc5414d671",
    "pl": "fac63e49c49ea2e39dd8a48152d7e54cec0920abbc59993088063ed5d9b528c2",
    "pt": "7d764586bca6262f554d5fa77ad8e6841ef42534776e70558065140853660ce2",
    "es": "14f326b4f68d517f9b8b99c1e26ef56a508d2dc8d0ee7a9e6e8732ddab1aa65e",
}

LANGUAGES = ("de", "en", "fr", "it", "nl", "pl", "pt", "es")
LANGUAGE_OF_TAG = {language: language for language in LANGUAGES} | {"pt-br": "pt"}
SHARED_TAG = "mul"
DEFAULT_MAX_TERMS = 3000
MAX_TERMS = {"medizin": 6000, "medikamente": 5000, "chemie": 5000}
ITEM_POOL_SIZE = 9000
QUERY_TIME_LIMIT_SECONDS = 60
CLIENT_TIMEOUT_SECONDS = QUERY_TIME_LIMIT_SECONDS + 10
PARALLEL_QUERIES = 3
MAX_ATTEMPTS = 8
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
LABEL_BATCH_SIZE = 250
COMMON_GERMAN_WORD_COUNT = 20000
COMMON_WORD_ZIPF = 4.0
COMMON_BUCKET = round((9 - COMMON_WORD_ZIPF) * 100)
CAPITALIZED_COMMON_ZIPF = 5.0
CAPITALIZED_COMMON_BUCKET = round((9 - CAPITALIZED_COMMON_ZIPF) * 100)
RAREST_BUCKET = 10 ** 6
MIN_TERM_LENGTH = 3
MAX_TERM_LENGTH = 60
MAX_TERM_WORDS = 4
SYNONYM_LIMIT = 2
COGNATE_MIN = 0.8
MIN_SYNONYM_LETTERS = 7
VARIANT_MIN = 0.9
DERIVED_PREFIX_SHARE = 0.75
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
OUTPUT_DIR = ASSETS_DIR / "fachwortschatz"
KNOWN_GERMAN_WORDS_FILE = ASSETS_DIR / "wordlist-de.txt"
SOURCE_NOTE = "QUELLEN.md"

GERMAN_WORD = re.compile(r"[a-zäöüß]+")
LETTER_RUN = re.compile(r"[^\W\d_]{3,}")
INNER_CAPITAL = re.compile(r".\S*[A-ZÄÖÜ]")
LIST_PAGE = re.compile(r"^(liste|list|lijst|lista|elenco)\s", re.IGNORECASE)
STEREO_PREFIX = re.compile(r"^(?:\((?:R|S|RS|SR|E|Z|EZ|R,S|S,R|±|\+|-|\+/-)\)-)+(?=[^\W\d_])")
ALLOWED_PUNCTUATION = frozenset(" -'./+&#")
EDGE_PUNCTUATION = "-/&'"
ENGLISH_FUNCTION_WORDS = frozenset({"of", "the", "and", "with", "for", "from", "without", "on"})
LEADING_ARTICLES = {
    "de": ("der", "die", "das"),
    "en": ("the",),
    "fr": ("le", "la", "les", "l'"),
    "it": ("il", "lo", "la", "gli", "le", "l'"),
    "nl": ("de", "het"),
    "pl": (),
    "pt": ("o", "os", "as"),
    "es": ("el", "la", "los", "las"),
}
LEADING_ALIAS_LIMIT = 2
INFLECTION_SUFFIXES = ("es", "en", "s", "n", "e")
SPELLING_VARIANTS = (
    ("ph", "f"), ("th", "t"), ("rh", "r"), ("ae", "e"), ("oe", "e"), ("qu", "c"), ("k", "c"), ("z", "c"), ("y", "i"),
)
UMLAUT_SPELLING = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})
WORD_TOKEN = re.compile(r"[^\W\d_]+")
ALPHABETS = {
    "de": "äöüß",
    "en": "",
    "fr": "àâæçéèêëîïôœùûüÿ",
    "it": "àèéìíîòóùú",
    "nl": "áàäéèëíïóöúü",
    "pl": "ąćęłńóśźż",
    "pt": "áâãàçéêíóôõú",
    "es": "áéíñóúü",
}
LATIN_RANGE = range(0xC0, 0x250)
GREEK_RANGE = range(0x370, 0x400)
TERM_TRANSLATION = (
    dict.fromkeys((0x09, 0x0A, 0x0D, 0xA0, 0x2002, 0x2003, 0x2007, 0x2009, 0x200A, 0x202F, 0x3000), " ")
    | dict.fromkeys((0xAD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF), None)
    | dict.fromkeys((0x2010, 0x2011, 0x2012, 0x2013, 0x2212), "-")
    | dict.fromkeys((0x2018, 0x2019, 0x02BC, 0xB4), "'")
)
KIND_ORDER = {"label": 0, "short": 1, "alias": 2}

MSGPACK_TEXT_WIDTHS = {0xD9: 1, 0xDA: 2, 0xDB: 4}
MSGPACK_ARRAY_WIDTHS = {0xDC: 2, 0xDD: 4}
MSGPACK_UINT_WIDTHS = {0xCC: 1, 0xCD: 2, 0xCE: 4}


@dataclass(frozen=True)
class Selector:
    classes: tuple[str, ...] = ()
    path: str = "P31"
    holds: str = ""
    items: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    excluded_prefixes: tuple[str, ...] = ()
    gate: tuple[str, ...] = ()
    excluded_classes: tuple[str, ...] = ()
    excluded_types: tuple[str, ...] = ()
    excluded_ancestors: tuple[str, ...] = ()
    excluded_properties: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()
    min_sitelinks: int = 1
    weight: float = 1.0
    languages: tuple[str, ...] = LANGUAGES


@dataclass(frozen=True)
class WordLists:
    frequency: dict[str, dict[str, int]]
    common_german: frozenset[str]
    known_german: frozenset[str]


def instances(*classes: str, **options) -> Selector:
    return Selector(classes=classes, path="P31", **options)


def subclasses(*classes: str, **options) -> Selector:
    return Selector(classes=classes, path="P279+", **options)


def near_subclasses(*classes: str, **options) -> Selector:
    return Selector(classes=classes, path="P279/P279?", **options)


def members(*classes: str, **options) -> Selector:
    return Selector(classes=classes, path="(P31|P279)/P279*", **options)


def holders(prop: str, *prefixes: str, **options) -> Selector:
    return Selector(holds=prop, prefixes=prefixes, **options)


def prefix_test(variable: str, prefixes: tuple[str, ...]) -> str:
    return " || ".join(f'STRSTARTS(STR({variable}), "{prefix}")' for prefix in prefixes)


DISEASE_IDS = ("P494", "P7807", "P493", "P699", "P486", "P604", "P557", "P673", "P5806")
ANATOMY_IDS = ("P1402", "P1323")
PROCEDURE_IDS = ("P1692", "P1690", "P5806", "P4338")
DRUG_IDS = ("P267", "P715")
NON_THERAPEUTIC_ATC = ("V01", "V03AN", "V07")
CHEMICAL_ELEMENT = "Q11344"
HUMAN = "Q5"
ORGANIZATION = "Q43229"
COURT = "Q41487"
INTERNATIONAL_COURT = "Q1262438"
CURRENCY_CODE = "P498"
TAXON_NAME = "P225"
GENE_ONTOLOGY = "P686"
WIKIMEDIA_PROJECT = "Q14827288"
WIKIPEDIA_EDITION = "Q10876391"
DISSOLVED = ("P576",)
REPEALED = ("P576", "P582")
TIME_BOUND = ("P580", "P582", "P585")
ENTITY_TRAITS = ("P856", "P159", "P625", "P571", *DISSOLVED, *TIME_BOUND)
MONEY_TYPES = ("Q1368", "Q8142", "Q41207", "Q113813711")
LIFE_SCIENCE_TYPES = ("Q112193867", "Q1441305", "Q2996394")
PHYSICS_IDS = ("P416", "P2534", "P4020", "P8855")
UNIT_IDS = ("P2370", "P7825", "P2968")
NATIONAL_COURT_MIN_SITELINKS = 5
BROAD_SOURCE_WEIGHT = 0.25
MESH_MEDICAL_BRANCHES = (
    "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A11", "A12", "A14", "A15", "A16", "A17",
    "C", "E01", "E02", "E03", "E04", "E06", "F03", "H02.403",
)
MESH_EXCLUDED_BRANCHES = ("E01.370.350.600", "E02.190.901", "F03.250.400")
LAW_CLASSES = (
    "Q820655", "Q922203", "Q1923776", "Q7755", "Q2076487", "Q6453643", "Q2703920", "Q3042975", "Q13408009",
    "Q4677783", "Q1006079", "Q16603799",
)
EXCLUDED_CLASSES = ("Q115305900", "Q870780")
EXCLUDED_ITEMS = frozenset({"Q248542", "Q1126839", "Q1977520", "Q25110971", "Q94638515", "Q134083964", "Q136549314"})


def national_laws(language: str, *countries: str) -> Selector:
    return instances(*LAW_CLASSES, jurisdictions=countries, excluded_properties=REPEALED, languages=(language,))


def national_courts(language: str, *countries: str) -> Selector:
    return members(COURT, jurisdictions=countries, excluded_properties=DISSOLVED,
                   min_sitelinks=NATIONAL_COURT_MIN_SITELINKS, languages=(language,))


DOMAINS: dict[str, tuple[Selector, ...]] = {
    "medizin": (
        instances("Q112193867"),
        instances("Q12136"),
        subclasses("Q12136", gate=DISEASE_IDS),
        instances("Q130753312"),
        subclasses("Q1441305", gate=DISEASE_IDS),
        members("Q169872", gate=DISEASE_IDS),
        instances("Q112826905", gate=ANATOMY_IDS),
        instances("Q103812529", gate=ANATOMY_IDS),
        subclasses("Q4936952", gate=ANATOMY_IDS),
        instances("Q55215251"),
        members("Q2671652", gate=PROCEDURE_IDS),
        members("Q796194", gate=PROCEDURE_IDS),
        members("Q15636229", gate=PROCEDURE_IDS),
        members("Q930752"),
        members("Q12135", gate=DISEASE_IDS),
        members("Q193078", gate=DISEASE_IDS),
        members("Q179630", gate=DISEASE_IDS),
        holders("P672", *MESH_MEDICAL_BRANCHES, excluded_prefixes=MESH_EXCLUDED_BRANCHES),
    ),
    "medikamente": (
        holders("P267", excluded_prefixes=NON_THERAPEUTIC_ATC, excluded_classes=(CHEMICAL_ELEMENT,)),
        instances("Q2585617"),
        members("Q12140", gate=DRUG_IDS, excluded_classes=(CHEMICAL_ELEMENT,)),
        members("Q134808"),
        holders("P672", "D27.505"),
        instances("Q28885102", min_sitelinks=0),
    ),
    "jura": (
        instances("Q1756157"),
        instances("Q2135465", excluded_ancestors=(ORGANIZATION,)),
        instances("Q130583773"),
        instances("Q131784846"),
        subclasses(COURT),
        members(INTERNATIONAL_COURT, excluded_properties=DISSOLVED),
        subclasses("Q158970"),
        subclasses("Q689247"),
        subclasses("Q697327"),
        subclasses("Q1301203", excluded_properties=TIME_BOUND),
        members("Q1938208"),
        members("Q3237872"),
        subclasses("Q8458"),
        members("Q10353985"),
        national_laws("de", "Q183"),
        national_courts("de", "Q183"),
        holders("P9696", languages=("de",)),
        national_laws("en", "Q145", "Q30"),
        national_courts("en", "Q145", "Q30"),
        holders("P3343", languages=("en",)),
        holders("P3837", languages=("en",)),
        national_laws("fr", "Q142"),
        national_courts("fr", "Q142"),
        national_laws("it", "Q38"),
        national_courts("it", "Q38"),
        holders("P8722", languages=("it",)),
        national_laws("nl", "Q55"),
        national_courts("nl", "Q55"),
        holders("P13979", languages=("nl",)),
        national_laws("pl", "Q36"),
        national_courts("pl", "Q36"),
        national_laws("pt", "Q45", "Q155"),
        national_courts("pt", "Q45", "Q155"),
        holders("P9119", languages=("pt",)),
        national_laws("es", "Q29"),
        national_courts("es", "Q29"),
        holders("P4256", languages=("es",)),
    ),
    "wirtschaft": (
        holders("P10715", excluded_classes=(HUMAN,), excluded_ancestors=(ORGANIZATION,),
                excluded_properties=ENTITY_TRAITS, weight=BROAD_SOURCE_WEIGHT),
        members("Q29028649"),
        subclasses("Q247506", excluded_types=MONEY_TYPES, excluded_properties=(CURRENCY_CODE,)),
        members("Q832161"),
        members("Q1167393"),
        subclasses("Q8161"),
        instances("Q130109687"),
        subclasses("Q273005", excluded_classes=(WIKIMEDIA_PROJECT,), excluded_types=(WIKIPEDIA_EDITION,)),
        subclasses("Q815823"),
        instances("Q1269299"),
        subclasses("Q192907"),
        subclasses("Q169489"),
        subclasses("Q43183"),
        subclasses("Q22687"),
        subclasses("Q189539"),
        members("Q1779838"),
        members("Q3048444"),
        members("Q1401304"),
        subclasses("Q208697"),
        subclasses("Q39809"),
        subclasses("Q2851421"),
        subclasses("Q4116214"),
        instances("Q64588497"),
        instances("Q116460050"),
        instances("Q106905561"),
        instances("Q64513545"),
        subclasses("Q8137"),
        subclasses("Q170924"),
        subclasses("Q1527264"),
        subclasses("Q1166072"),
        subclasses("Q160151"),
    ),
    "technik": (
        members("Q107715", gate=PHYSICS_IDS),
        members("Q47574", gate=UNIT_IDS, excluded_properties=(CURRENCY_CODE,)),
        holders("P7825"),
        members("Q214070"),
        near_subclasses("Q1293220"),
        instances("Q125517960"),
        subclasses("Q11653"),
        holders("P8855", excluded_types=LIFE_SCIENCE_TYPES, excluded_properties=(GENE_ONTOLOGY,)),
        near_subclasses("Q839546"),
        subclasses("Q2041172"),
        members("Q1408288"),
        instances("Q4162444"),
        subclasses("Q11023"),
        near_subclasses("Q44167"),
        instances("Q173227"),
        instances("Q140424281"),
        instances("Q137582043"),
        subclasses("Q1480529"),
    ),
    "chemie": (
        instances(CHEMICAL_ELEMENT),
        holders("P231", min_sitelinks=3, excluded_properties=(TAXON_NAME,)),
        members("Q36534"),
        members("Q44424"),
        members("Q170409"),
        instances("Q11790203"),
        subclasses("Q834028"),
        members("Q898987"),
        members("Q2281940"),
        members("Q764285"),
        instances("Q55640599"),
        near_subclasses("Q81163"),
        subclasses("Q37756"),
        instances("Q47154513"),
        instances("Q56256173"),
        instances("Q4751159"),
        instances("Q3247516"),
        subclasses("Q71550700"),
    ),
    "it": (
        members("Q9143"),
        members("Q9135"),
        members("Q6368"),
        members("Q235557"),
        members("Q15836568"),
        members("Q132364"),
        members("Q188860"),
        members("Q271680"),
        members("Q1330336"),
        members("Q175263"),
        members("Q8366"),
        members("Q188267"),
        members("Q37045"),
        members("Q845739"),
        members("Q174989"),
        members("Q13741"),
        members("Q131212"),
        members("Q3257930"),
        members("Q176165"),
        instances("Q17155032"),
        instances("Q66747126"),
        members("Q14001"),
        subclasses("Q3966"),
        members("Q181156"),
        subclasses("Q4071928"),
        members("Q11288"),
        members("Q11189"),
        members("Q71550"),
        members("Q7935198"),
        members("Q118218718"),
        members("Q1077480"),
        members("Q16947796"),
        members("Q29032804"),
        members("Q138081337"),
        members("Q13224353"),
        members("Q1480561"),
        members("Q141089604"),
        members("Q91348108"),
        members("Q1092177"),
        members("Q756230"),
        members("Q14663"),
        members("Q891055"),
        members("Q2727468"),
        members("Q47506"),
    ),
}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def entity_list(ids: tuple[str, ...]) -> str:
    return " ".join(f"wd:{entity}" for entity in ids)


def match_clause(selector: Selector) -> str:
    if selector.items:
        return f"VALUES ?item {{ {entity_list(selector.items)} }}"
    if selector.holds:
        if not selector.prefixes:
            return f"?item wdt:{selector.holds} [] ."
        return f"?item wdt:{selector.holds} ?value . FILTER({prefix_test('?value', selector.prefixes)})"
    path = re.sub(r"P\d+", lambda found: "wdt:" + found.group(), selector.path)
    if len(selector.classes) == 1:
        return f"?item {path} wd:{selector.classes[0]} ."
    return f"VALUES ?class {{ {entity_list(selector.classes)} }} ?item {path} ?class ."


def selector_query(selector: Selector) -> str:
    clauses = [match_clause(selector)]
    if selector.jurisdictions:
        places = entity_list(selector.jurisdictions)
        clauses.append(f"FILTER EXISTS {{ VALUES ?place {{ {places} }} ?item wdt:P1001|wdt:P17 ?place . }}")
    if selector.excluded_prefixes:
        test = prefix_test("?other", selector.excluded_prefixes)
        clauses.append(f"FILTER NOT EXISTS {{ ?item wdt:{selector.holds} ?other . FILTER({test}) }}")
    if selector.gate:
        alternatives = "|".join(f"wdt:{prop}" for prop in selector.gate)
        clauses.append(f"FILTER EXISTS {{ ?item {alternatives} [] }}")
    for excluded in EXCLUDED_CLASSES:
        clauses.append(f"FILTER NOT EXISTS {{ ?item wdt:P31 wd:{excluded} }}")
    for excluded in selector.excluded_classes:
        clauses.append(f"FILTER NOT EXISTS {{ ?item wdt:P31/wdt:P279* wd:{excluded} }}")
    if selector.excluded_types:
        types = entity_list(selector.excluded_types)
        clauses.append(f"FILTER NOT EXISTS {{ VALUES ?type {{ {types} }} ?item wdt:P31|wdt:P279 ?type . }}")
    for ancestor in selector.excluded_ancestors:
        clauses.append(
            "FILTER NOT EXISTS { ?item wdt:P279 ?parent . ?parent wdt:P279? ?grandparent . "
            f"?grandparent wdt:P279? wd:{ancestor} . }}"
        )
    if selector.excluded_properties:
        alternatives = "|".join(f"wdt:{prop}" for prop in selector.excluded_properties)
        clauses.append(f"FILTER NOT EXISTS {{ ?item {alternatives} [] }}")
    clauses.append("?item wikibase:sitelinks ?links .")
    clauses.append(f"FILTER(?links >= {selector.min_sitelinks})")
    body = "\n  ".join(clauses)
    return f"SELECT DISTINCT ?item ?links WHERE {{\n  {body}\n}}"


def retry_delay(retry_after: str | None, attempt: int) -> float:
    if retry_after and retry_after.strip().isdigit():
        return int(retry_after.strip()) + 1
    return min(60, 2 ** attempt)


def http_get(url: str, data: bytes | None = None, accept: str = "*/*") -> bytes:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(request, timeout=CLIENT_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read()[:2000].decode("utf-8", "replace")
            if "TimeoutException" in detail:
                raise RuntimeError(f"Abfrage länger als {QUERY_TIME_LIMIT_SECONDS} s abgebrochen") from error
            if error.code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"HTTP {error.code}: {detail[:300]}") from error
            delay = retry_delay(error.headers.get("Retry-After"), attempt)
            reason = f"HTTP {error.code}"
        except (TimeoutError, urllib.error.URLError, http.client.HTTPException) as error:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"Verbindung fehlgeschlagen: {error}") from error
            delay = retry_delay(None, attempt)
            reason = type(error).__name__
        log(f"  Wiederholung {attempt} in {delay:.0f} s ({reason})")
        time.sleep(delay)
    raise RuntimeError("keine Antwort")


def run_query(query: str, cache_dir: Path | None) -> list[dict]:
    cache_file = cache_dir / f"{hashlib.sha256(query.encode()).hexdigest()}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.monotonic()
        payload = http_get(SPARQL_ENDPOINT, data=body, accept="application/sparql-results+json")
        try:
            rows = json.loads(payload)["results"]["bindings"]
            break
        except (json.JSONDecodeError, KeyError) as error:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError("Antwort unvollständig") from error
            delay = retry_delay(None, attempt)
            log(f"  Antwort unvollständig, Wiederholung {attempt} in {delay:.0f} s")
            time.sleep(delay)
    log(f"  {len(rows)} Zeilen in {time.monotonic() - started:.1f} s")
    if cache_file:
        cache_file.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def entity_id(binding: dict) -> str:
    return binding["value"].rsplit("/", 1)[-1]


def decode_msgpack(payload: bytes, position: int = 0) -> tuple[object, int]:
    marker = payload[position]
    position += 1
    if marker <= 0x7F:
        return marker, position
    if marker <= 0x8F:
        pairs, position = decode_sequence(payload, position, 2 * (marker & 0x0F))
        return dict(zip(pairs[::2], pairs[1::2])), position
    if marker <= 0x9F:
        return decode_sequence(payload, position, marker & 0x0F)
    if marker <= 0xBF:
        return decode_text(payload, position, marker & 0x1F)
    for widths, reader in ((MSGPACK_TEXT_WIDTHS, decode_text), (MSGPACK_ARRAY_WIDTHS, decode_sequence)):
        if marker in widths:
            width = widths[marker]
            return reader(payload, position + width, int.from_bytes(payload[position:position + width], "big"))
    if marker in MSGPACK_UINT_WIDTHS:
        width = MSGPACK_UINT_WIDTHS[marker]
        return int.from_bytes(payload[position:position + width], "big"), position + width
    raise ValueError(f"msgpack-Kennung {marker:#04x} nicht unterstützt")


def decode_sequence(payload: bytes, position: int, count: int) -> tuple[list, int]:
    values = []
    for _ in range(count):
        value, position = decode_msgpack(payload, position)
        values.append(value)
    return values, position


def decode_text(payload: bytes, position: int, length: int) -> tuple[str, int]:
    end = position + length
    return payload[position:end].decode("utf-8"), end


def load_word_frequencies(cache_dir: Path | None) -> dict[str, dict[str, int]]:
    frequencies = {}
    for language in LANGUAGES:
        cache_file = cache_dir / f"wordfreq-large_{language}.msgpack.gz" if cache_dir else None
        if cache_file and cache_file.exists():
            compressed = cache_file.read_bytes()
        else:
            compressed = http_get(WORDFREQ_URL.format(commit=WORDFREQ_COMMIT, language=language))
            if cache_file:
                cache_file.write_bytes(compressed)
        if hashlib.sha256(compressed).hexdigest() != WORDFREQ_SHA256[language]:
            raise RuntimeError(f"Prüfsumme der wordfreq-Daten ({language}) stimmt nicht")
        table, _ = decode_msgpack(gzip.decompress(compressed))
        header, *buckets = table
        if not isinstance(header, dict) or header.get("format") != "cB":
            raise RuntimeError(f"unerwartetes Format der wordfreq-Daten ({language})")
        ranks: dict[str, int] = {}
        for bucket, words in enumerate(buckets):
            for word in words:
                ranks.setdefault(word, bucket)
        frequencies[language] = ranks
    return frequencies


def common_german_words(frequency: dict[str, int]) -> frozenset[str]:
    ranked = (word for word in frequency if GERMAN_WORD.fullmatch(word))
    return frozenset(itertools.islice(ranked, COMMON_GERMAN_WORD_COUNT))


def domain_selectors(domain: str) -> tuple[Selector, ...]:
    selectors = DOMAINS[domain]
    roots = tuple(dict.fromkeys(entity for selector in selectors if selector.path != "P31" for entity in selector.classes))
    return selectors + (Selector(items=roots),) if roots else selectors


def collect_items(selectors: tuple[Selector, ...], cache_dir: Path | None) -> list[dict[str, int]]:
    def fetch(selector: Selector) -> dict[str, int]:
        rows = run_query(selector_query(selector), cache_dir)
        return {entity_id(row["item"]): int(row["links"]["value"]) for row in rows}

    with ThreadPoolExecutor(PARALLEL_QUERIES) as pool:
        return list(pool.map(fetch, selectors))


def build_pools(selectors: tuple[Selector, ...], found: list[dict[str, int]]) -> dict[str, dict[str, float]]:
    pools = {}
    for language in LANGUAGES:
        merged: dict[str, float] = {}
        for selector, items in zip(selectors, found):
            if language not in selector.languages:
                continue
            for item, links in items.items():
                if item not in EXCLUDED_ITEMS and links * selector.weight > merged.get(item, -1):
                    merged[item] = links * selector.weight
        ranked = sorted(merged.items(), key=lambda entry: (-entry[1], int(entry[0][1:])))
        pools[language] = dict(ranked[:ITEM_POOL_SIZE])
    return pools


def label_query(item_ids: list[str]) -> str:
    tags = ", ".join(f'"{tag}"' for tag in (*LANGUAGE_OF_TAG, SHARED_TAG))
    return (
        "SELECT ?item ?term ?kind WHERE {\n"
        f"  VALUES ?item {{ {entity_list(tuple(item_ids))} }}\n"
        '  VALUES (?predicate ?kind) { (rdfs:label "label") (skos:altLabel "alias") (wdt:P1813 "short") }\n'
        "  ?item ?predicate ?term .\n"
        f"  FILTER(LANG(?term) IN ({tags}))\n"
        "}"
    )


def fetch_terms(item_ids: list[str], cache_dir: Path | None) -> dict[str, dict[str, list[tuple[str, str]]]]:
    cache_file = cache_dir / "labels.json" if cache_dir else None
    stored: dict[str, list[list[str]]] = {}
    if cache_file and cache_file.exists():
        stored = json.loads(cache_file.read_text(encoding="utf-8"))
    missing = sorted((item for item in item_ids if item not in stored), key=lambda entity: int(entity[1:]))
    batches = [missing[start:start + LABEL_BATCH_SIZE] for start in range(0, len(missing), LABEL_BATCH_SIZE)]
    with ThreadPoolExecutor(PARALLEL_QUERIES) as pool:
        results = list(pool.map(lambda batch: run_query(label_query(batch), None), batches))
    for item in missing:
        stored[item] = []
    for row in itertools.chain.from_iterable(results):
        stored[entity_id(row["item"])].append(
            [row["term"].get("xml:lang", ""), row["term"]["value"], row["kind"]["value"]]
        )
    if cache_file and missing:
        cache_file.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
    terms: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for item in item_ids:
        for tag, text, kind in stored.get(item, []):
            language = SHARED_TAG if tag == SHARED_TAG else LANGUAGE_OF_TAG.get(tag)
            if language:
                terms.setdefault(item, {}).setdefault(language, []).append((text, kind))
    return terms


def terms_for_language(item_terms: dict[str, list[tuple[str, str]]], language: str) -> list[tuple[str, str]]:
    own = item_terms.get(language, [])
    shared = item_terms.get(SHARED_TAG, [])
    if any(kind == "label" for _, kind in own):
        shared = [(text, kind) for text, kind in shared if kind != "label"]
    return own + shared


def normalize_term(text: str) -> str:
    term = " ".join(unicodedata.normalize("NFC", text).translate(TERM_TRANSLATION).split())
    return STEREO_PREFIX.sub("", term)


def letter_script(character: str) -> str:
    if character.isascii() or ord(character) in LATIN_RANGE:
        return "latin"
    if ord(character) in GREEK_RANGE:
        return "greek"
    return "other"


def has_acceptable_characters(term: str) -> bool:
    scripts = set()
    for character in term:
        if character.isalpha():
            scripts.add(letter_script(character))
        elif not (character.isascii() and character.isdigit()) and character not in ALLOWED_PUNCTUATION:
            return False
    return "latin" in scripts and "other" not in scripts


def looks_like_code(term: str) -> bool:
    letters = sum(character.isalpha() for character in term)
    digits = sum(character.isdigit() for character in term)
    return digits * 2 > letters


def starts_with_article(term: str, language: str) -> bool:
    first = term.split(" ", 1)[0].lower()
    articles = LEADING_ARTICLES[language]
    return first in articles or any(article.endswith("'") and first.startswith(article) for article in articles)


def word_bucket(term: str, language: str, word_lists: WordLists) -> int:
    return word_lists.frequency[language].get(term.casefold(), RAREST_BUCKET)


def is_common_word(term: str, language: str, word_lists: WordLists) -> bool:
    if " " in term or INNER_CAPITAL.match(term):
        return False
    if language == "de":
        return term.casefold() in word_lists.common_german
    limit = COMMON_BUCKET if term == term.lower() else CAPITALIZED_COMMON_BUCKET
    return word_bucket(term, language, word_lists) <= limit


def accept_term(term: str, kind: str, language: str, word_lists: WordLists) -> bool:
    words = term.split(" ")
    return (
        MIN_TERM_LENGTH <= len(term) <= MAX_TERM_LENGTH
        and len(words) <= MAX_TERM_WORDS
        and "-" not in words
        and has_acceptable_characters(term)
        and not term.startswith(tuple(EDGE_PUNCTUATION))
        and not term.endswith(tuple(EDGE_PUNCTUATION))
        and not looks_like_code(term)
        and not LIST_PAGE.match(term)
        and not starts_with_article(term, language)
        and (kind == "label" or LETTER_RUN.search(term) is not None)
        and (language == "en" or not ENGLISH_FUNCTION_WORDS.intersection(word.lower() for word in words))
        and not is_common_word(term, language, word_lists)
    )


def is_redundant_alias(
    term: str, own_keys: set[str], label_keys: set[str], english_keys: set[str], language: str, word_lists: WordLists
) -> bool:
    key = term.casefold()
    if letters_only(term) in english_keys:
        return True
    if any(label != key and re.search(rf"(?<!\w){re.escape(label)}(?!\w)", key) for label in label_keys):
        return True
    if any(key.endswith(suffix) and key[: -len(suffix)] in own_keys for suffix in INFLECTION_SUFFIXES):
        return True
    return language == "de" and " " not in term and (term == term.lower() or key in word_lists.known_german)


def letters_only(text: str) -> str:
    return "".join(character for character in text.casefold() if character.isalpha())


def label_similarity(alias: str, label_keys: set[str]) -> float:
    key = alias.casefold()
    return max((difflib.SequenceMatcher(None, key, label).ratio() for label in label_keys), default=0.0)


def flat_spelling(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold().translate(UMLAUT_SPELLING))
    letters = "".join(character for character in decomposed if character.isalpha())
    for old, new in SPELLING_VARIANTS:
        letters = letters.replace(old, new)
    return letters


def best_similarity(form: str, others: list[str]) -> float:
    best = 0.0
    for other in others:
        matcher = difflib.SequenceMatcher(None, form, other, autojunk=False)
        if matcher.real_quick_ratio() > best and matcher.quick_ratio() > best:
            best = max(best, matcher.ratio())
    return best


def foreign_label_forms(item_terms: dict[str, list[tuple[str, str]]], language: str) -> list[str]:
    forms = (
        flat_spelling(normalize_term(text))
        for tag, entries in item_terms.items() if tag != language
        for text, kind in entries if kind == "label"
    )
    return [form for form in dict.fromkeys(forms) if form]


def is_derived(alias: str, labels: list[str], language: str, word_lists: WordLists) -> bool:
    key = letters_only(alias)
    bucket = word_bucket(alias, language, word_lists)
    for label in labels:
        other = letters_only(label)
        shorter = min(len(key), len(other))
        if not shorter or key == other or bucket < word_bucket(label, language, word_lists):
            continue
        if len(os.path.commonprefix((key, other))) >= DERIVED_PREFIX_SHARE * shorter:
            return True
    return False


def in_alphabet(term: str, language: str) -> bool:
    extra = ALPHABETS[language]
    return all(character.isascii() or character in extra for character in term.casefold() if character.isalpha())


def is_attested(term: str, language: str, word_lists: WordLists) -> bool:
    words = WORD_TOKEN.findall(term.casefold())
    return bool(words) and all(word in word_lists.frequency[language] for word in words)


def technical_synonyms(
    aliases: list[str],
    labels: list[str],
    item_terms: dict[str, list[tuple[str, str]]],
    language: str,
    word_lists: WordLists,
) -> list[str]:
    foreign = foreign_label_forms(item_terms, language)
    if not foreign or not aliases:
        return []
    label_forms = [flat_spelling(label) for label in labels]
    candidates = []
    for alias in aliases:
        form = flat_spelling(alias)
        closeness = best_similarity(form, label_forms) if form else 1.0
        if closeness >= VARIANT_MIN:
            continue
        if len(letters_only(alias)) < MIN_SYNONYM_LETTERS or any(character.isdigit() for character in alias):
            continue
        if is_derived(alias, labels, language, word_lists) or not in_alphabet(alias, language):
            continue
        if not is_attested(alias, language, word_lists):
            continue
        score = round(best_similarity(form, foreign), 2)
        if score >= COGNATE_MIN:
            bucket = word_bucket(alias, language, word_lists)
            candidates.append((-score, bucket, -round(closeness, 2), len(alias), alias, form))
    clusters: list[list[tuple]] = []
    for candidate in sorted(candidates):
        for cluster in clusters:
            if best_similarity(candidate[-1], [member[-1] for member in cluster]) >= VARIANT_MIN:
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])
    choices = []
    for cluster in clusters:
        chosen = min(cluster, key=lambda member: (member[1], member[2], member[0], member[3], member[4]))
        choices.append((cluster[0][0], chosen[1], chosen[3], chosen[4]))
    return [alias for *_, alias in sorted(choices)[:SYNONYM_LIMIT]]


def alphabetical_key(term: str) -> str:
    decomposed = unicodedata.normalize("NFKD", term.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def first_unique(candidates: list[tuple], limit: int) -> list[str]:
    ranked: list[str] = []
    seen: set[str] = set()
    for *_, term in candidates:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            ranked.append(term)
            if len(ranked) == limit:
                break
    return ranked


def rank_terms(
    pool: dict[str, float],
    terms: dict[str, dict[str, list[tuple[str, str]]]],
    language: str,
    word_lists: WordLists,
    limit: int,
) -> list[str]:
    leading: list[tuple] = []
    trailing: list[tuple] = []
    for item, links in pool.items():
        item_terms = terms.get(item, {})
        entries = [(normalize_term(text), kind) for text, kind in terms_for_language(item_terms, language)]
        labels = [term for term, kind in entries if kind == "label"]
        usable_label = any(accept_term(term, "label", language, word_lists) for term in labels)
        everyday_label = any(is_common_word(term, language, word_lists) for term in labels)
        english_keys = set()
        if language != "en":
            english_keys = {letters_only(normalize_term(text)) for text, _ in item_terms.get("en", [])}
        own_keys = {term.casefold() for term, kind in entries if kind != "alias"}
        label_keys = {term.casefold() for term in labels}
        aliases: list[str] = []
        for term, kind in entries:
            if not accept_term(term, kind, language, word_lists):
                continue
            if kind == "label" or (kind == "short" and not everyday_label):
                leading.append((-links, alphabetical_key(term), KIND_ORDER[kind], term))
            elif kind == "short":
                trailing.append((-links, alphabetical_key(term), KIND_ORDER[kind], term))
            elif not is_redundant_alias(term, own_keys, label_keys, english_keys, language, word_lists):
                aliases.append(term)
        aliases = list(dict.fromkeys(aliases))
        generic = any(" " not in label and word_bucket(label, language, word_lists) <= COMMON_BUCKET for label in labels)
        synonyms = [] if generic else technical_synonyms(aliases, labels, item_terms, language, word_lists)
        others = sorted(
            (alias for alias in aliases if alias not in synonyms),
            key=lambda alias: (-label_similarity(alias, label_keys), len(alias), alias),
        )
        lead_count = 0 if usable_label or everyday_label else max(0, LEADING_ALIAS_LIMIT - len(synonyms))
        for position, term in enumerate(synonyms + others):
            tier = leading if position < len(synonyms) + lead_count else trailing
            tier.append((-links, alphabetical_key(term), KIND_ORDER["alias"], term))
    return first_unique(sorted(leading) + sorted(trailing), limit)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")


def load_known_german_words() -> frozenset[str]:
    lines = KNOWN_GERMAN_WORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().casefold() for line in lines if line.strip() and not line.startswith("#"))


def term_limit(domain: str) -> int:
    return MAX_TERMS.get(domain, DEFAULT_MAX_TERMS)


def build_domain(domain: str, out_dir: Path, cache_dir: Path | None, word_lists: WordLists) -> None:
    selectors = domain_selectors(domain)
    log(f"{domain}: {len(selectors)} Klassenabfragen")
    found = collect_items(selectors, cache_dir)
    pools = build_pools(selectors, found)
    item_ids = sorted(set().union(*pools.values()), key=lambda entity: int(entity[1:]))
    log(f"{domain}: Bezeichnungen für {len(item_ids)} Einträge")
    terms = fetch_terms(item_ids, cache_dir)
    for language in LANGUAGES:
        ranked = rank_terms(pools[language], terms, language, word_lists, term_limit(domain))
        write_lines(out_dir / f"{domain}-{language}.txt", ranked)
        log(f"{domain}-{language}: {len(ranked)} Begriffe")


def describe_selector(selector: Selector, names: dict[str, str]) -> str:
    def named(entity: str) -> str:
        return f"{entity} {names[entity]}" if names.get(entity) else entity

    if selector.items:
        text = "Einträge " + ", ".join(named(entity) for entity in selector.items)
    elif selector.holds:
        text = f"Einträge mit {named(selector.holds)}"
        if selector.prefixes:
            text += " (Wert beginnt mit " + ", ".join(selector.prefixes) + ")"
    else:
        relation = {
            "P31": "Instanzen von",
            "P279+": "Unterklassen von",
            "P279/P279?": "Unterklassen bis zur zweiten Ebene von",
            "(P31|P279)/P279*": "Instanzen und Unterklassen von",
        }[selector.path]
        if selector.classes == LAW_CLASSES:
            text = f"{relation} den Gesetzesklassen"
        else:
            text = f"{relation} " + ", ".join(named(entity) for entity in selector.classes)
    if selector.jurisdictions:
        text += "; Geltungsbereich oder Staat " + ", ".join(named(entity) for entity in selector.jurisdictions)
    if selector.excluded_prefixes:
        text += "; ohne Werte ab " + ", ".join(selector.excluded_prefixes)
    if selector.gate:
        text += "; nur mit " + ", ".join(selector.gate)
    if selector.excluded_classes:
        text += "; ohne Instanzen von " + ", ".join(named(entity) for entity in selector.excluded_classes)
        text += " und deren Unterklassen"
    if selector.excluded_types:
        text += "; ohne direkte Instanzen und Unterklassen von "
        text += ", ".join(named(entity) for entity in selector.excluded_types)
    if selector.excluded_ancestors:
        text += "; ohne Unterklassen bis zur dritten Ebene von "
        text += ", ".join(named(entity) for entity in selector.excluded_ancestors)
    if selector.excluded_properties:
        text += "; ohne " + ", ".join(selector.excluded_properties)
    if selector.weight != 1:
        text += f"; Sitelinks zählen mit dem Faktor {german_number(selector.weight)}"
    if selector.min_sitelinks == 0:
        text += "; auch ohne Sitelinks"
    elif selector.min_sitelinks != 1:
        text += f"; mindestens {selector.min_sitelinks} Sitelinks"
    if selector.languages != LANGUAGES:
        text += "; nur für " + ", ".join(selector.languages)
    return text


def entity_names(cache_dir: Path | None) -> dict[str, str]:
    entities: set[str] = set(EXCLUDED_CLASSES)
    for selectors in DOMAINS.values():
        for selector in selectors:
            entities.update(selector.classes, selector.gate, selector.jurisdictions, selector.excluded_classes,
                            selector.excluded_types, selector.excluded_ancestors, selector.excluded_properties)
            if selector.holds:
                entities.add(selector.holds)
    query = (
        "SELECT ?entity ?label WHERE {\n"
        f"  VALUES ?entity {{ {entity_list(tuple(sorted(entities)))} }}\n"
        '  ?entity rdfs:label ?label . FILTER(LANG(?label) IN ("de", "en"))\n'
        "}"
    )
    names: dict[str, tuple[int, str]] = {}
    for row in run_query(query, cache_dir):
        entity = entity_id(row["entity"])
        rank = 0 if row["label"].get("xml:lang") == "de" else 1
        if entity not in names or rank < names[entity][0]:
            names[entity] = (rank, row["label"]["value"])
    return {entity: label for entity, (_, label) in names.items()}


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def german_number(value: float) -> str:
    return f"{value:,}".replace(",", " ").replace(".", ",").replace(" ", ".")


def write_source_note(out_dir: Path, cache_dir: Path | None, retrieval_date: datetime.date) -> None:
    names = entity_names(cache_dir)
    excluded = ", ".join(f"{entity} {names.get(entity, '')}".strip() for entity in EXCLUDED_CLASSES)
    limits = ", ".join(f"{domain} {german_number(limit)}" for domain, limit in MAX_TERMS.items())
    lines = [
        "# Quellen des Fachwortschatzes",
        "",
        "- Quelle: Wikidata, https://www.wikidata.org, Abfragen über https://query.wikidata.org/sparql",
        f"- Lizenz: CC0 1.0, {LICENSE_URL}",
        f"- Abrufdatum: {retrieval_date.isoformat()}",
        "- Erzeugt mit `scripts/build_fachwortschatz.py`",
        "",
        "## Auswahl",
        "",
        "- Begriffe: Bezeichnung (rdfs:label) und Kurzname (P1813) in der Sprache der Datei, ersatzweise die",
        "  sprachübergreifende Bezeichnung (mul). Stereodeskriptoren am Anfang wie „(RS)-“ oder „(±)-“ entfallen.",
        "- Die Oberklassen der Abfragen nach Unterklassen zählen selbst als Einträge.",
        f"- Fachsynonyme: bis zu {SYNONYM_LIMIT} Aliasse (skos:altLabel) je Eintrag stehen direkt bei der Bezeichnung, außer bei",
        f"  Einträgen, deren Bezeichnung ein Einzelwort ab Zipf {german_number(COMMON_WORD_ZIPF)} ist,",
        "  wenn sie der Bezeichnung desselben Eintrags in einer anderen Sprache ähneln (Ähnlichkeit ab",
        f"  {german_number(COGNATE_MIN)} nach Angleichung der Schreibung ä/ae, ö/oe, ü/ue, ph/f, th/t, rh/r, ae/oe/e, qu/k/z/c, y/i),",
        f"  mindestens {MIN_SYNONYM_LETTERS} Buchstaben und keine Ziffern haben, nur Buchstaben der Sprache der Datei enthalten",
        "  und jedes ihrer Wörter in den wordfreq-Daten dieser Sprache vorkommt. Schreibvarianten der Bezeichnung",
        f"  (Ähnlichkeit ab {german_number(VARIANT_MIN)}) und seltenere Ableitungen von ihr (gemeinsamer Wortanfang über",
        f"  mindestens {german_number(DERIVED_PREFIX_SHARE)} des kürzeren Begriffs) zählen nicht; von mehreren Schreibvarianten bleibt",
        "  die in wordfreq häufigere.",
        "- Übrige Aliasse stehen hinter allen Bezeichnungen. Hat ein Eintrag keine verwendbare Bezeichnung",
        f"  und ist diese kein Alltagswort, rücken bis zu {LEADING_ALIAS_LIMIT} Aliasse an ihre Stelle. Kurznamen von",
        "  Einträgen, deren Bezeichnung ein Alltagswort ist, stehen ebenfalls hinten.",
        "- Aliasse entfallen, wenn sie Buchstabe für Buchstabe einem englischen Begriff des Eintrags gleichen, die",
        "  Bezeichnung nur erweitern oder beugen.",
        "- Reihenfolge: Zahl der Sitelinks des Eintrags, bei Gleichstand alphabetisch; findet nur eine Abfrage mit",
        "  Gewichtsfaktor den Eintrag, zählen seine Sitelinks mit diesem Faktor. Höchstens so viele Begriffe je",
        f"  Datei: {limits}, sonst {german_number(DEFAULT_MAX_TERMS)}.",
        f"- Form: {MIN_TERM_LENGTH} bis {MAX_TERM_LENGTH} Zeichen, höchstens {MAX_TERM_WORDS} Wörter, lateinische und"
        " griechische Buchstaben,",
        "  keine Klammern, Kommas oder ziffernlastigen Kennungen.",
        f"- Alltagswörter (wordfreq {WORDFREQ_RELEASE}, https://github.com/rspeer/wordfreq, Daten CC BY-SA 4.0): Deutsch ohne",
        f"  die {german_number(COMMON_GERMAN_WORD_COUNT)} häufigsten Wörter, außer Wörtern mit Großbuchstaben im Wortinneren; übrige",
        f"  Sprachen ohne kleingeschriebene Einzelwörter ab Zipf {german_number(COMMON_WORD_ZIPF)} und großgeschriebene ab Zipf"
        f" {german_number(CAPITALIZED_COMMON_ZIPF)}. Die Häufigkeiten dienen nur als",
        "  Filter und zur Wahl zwischen Schreibvarianten, kein Wort daraus ist übernommen. Deutsche Aliasse zusätzlich",
        "  ohne Einzelwörter aus `assets/wordlist-de.txt`.",
        f"- Ausgeschlossen: Instanzen von {excluded}. Einzeln ausgeschlossen, weil ihre Bezeichnungen mit",
        "  Produkt- oder Personennamen zusammenfallen: " + ", ".join(sorted(EXCLUDED_ITEMS, key=lambda e: int(e[1:]))) + ".",
        "",
        "## Klassen je Fachgebiet",
    ]
    for domain, selectors in DOMAINS.items():
        lines += ["", f"### {domain}", ""]
        lines += [f"- {describe_selector(selector, names)}" for selector in selectors]
    lines += ["", "Gesetzesklassen: " + ", ".join(f"{entity} {names.get(entity, '')}".strip()
                                                for entity in LAW_CLASSES) + "."]
    properties = sorted(
        {prop for selectors in DOMAINS.values() for selector in selectors
         for prop in (*selector.gate, *selector.excluded_properties)},
        key=lambda entity: int(entity[1:]),
    )
    lines += ["", "Eigenschaften in den Filtern: " + ", ".join(f"{prop} {names.get(prop, '')}".strip()
                                                             for prop in properties) + "."]
    lines += ["", "## Begriffe je Datei", "", "| Gebiet | " + " | ".join(LANGUAGES) + " |",
              "|---|" + "---:|" * len(LANGUAGES)]
    for domain in DOMAINS:
        counts = [str(count_lines(out_dir / f"{domain}-{language}.txt")) for language in LANGUAGES]
        lines.append(f"| {domain} | " + " | ".join(counts) + " |")
    write_lines(out_dir / SOURCE_NOTE, lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fachwortschatz aus Wikidata erzeugen")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--domains", nargs="+", choices=sorted(DOMAINS), default=list(DOMAINS))
    parser.add_argument("--retrieval-date", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.cache_dir:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
    frequencies = load_word_frequencies(args.cache_dir)
    word_lists = WordLists(frequencies, common_german_words(frequencies["de"]), load_known_german_words())
    for domain in args.domains:
        build_domain(domain, args.out_dir, args.cache_dir, word_lists)
    write_source_note(args.out_dir, args.cache_dir, args.retrieval_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
