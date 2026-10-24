"""Testy blueprintow powiadomien: struktura YAML oraz renderowanie szablonow na realnych danych.

Nie wymagaja Home Assistanta - tylko pyyaml i jinja2. Blueprint jest wczytywany z tagiem
`!input`, wejscia sa podstawiane (domyslne albo nadpisane w tescie), a warunki i tresc
powiadomienia renderowane ze StrictUndefined, wiec literowka w nazwie pola konczy sie bledem.
"""
import re
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

KATALOG = Path(__file__).resolve().parent.parent / "blueprints" / "automation" / "librus_apix"
SENSOR_PY = Path(__file__).resolve().parent.parent / "custom_components" / "librus_apix" / "sensor.py"
PLIKI = sorted(KATALOG.glob("*.yaml"))


class Wejscie:
    """Wartosc tagu !input."""

    def __init__(self, nazwa):
        self.nazwa = nazwa


class _Loader(yaml.SafeLoader):
    uzyte = None


def _input(loader, node):
    nazwa = loader.construct_scalar(node)
    loader.uzyte.append(nazwa)
    return Wejscie(nazwa)


_Loader.add_constructor("!input", _input)


def wczytaj(sciezka):
    loader = _Loader(sciezka.read_text(encoding="utf-8"))
    loader.uzyte = []
    try:
        dane = loader.get_single_data()
    finally:
        loader.dispose()
    return dane, loader.uzyte


def podstaw(obj, wejscia):
    if isinstance(obj, Wejscie):
        return wejscia[obj.nazwa]
    if isinstance(obj, dict):
        return {k: podstaw(v, wejscia) for k, v in obj.items()}
    if isinstance(obj, list):
        return [podstaw(v, wejscia) for v in obj]
    return obj


def _szablon(tekst):
    return isinstance(tekst, str) and ("{{" in tekst or "{%" in tekst)


class Srodowisko:
    def __init__(self, stany):
        def state_attr(entity, atrybut):
            return stany.get(entity, {}).get(atrybut)

        self.tekst = Environment(undefined=StrictUndefined)
        self.natywne = NativeEnvironment(undefined=StrictUndefined)
        for env in (self.tekst, self.natywne):
            env.globals["state_attr"] = state_attr

    def tresc(self, wartosc, ctx):
        if isinstance(wartosc, dict):
            return {k: self.tresc(v, ctx) for k, v in wartosc.items()}
        if not _szablon(wartosc):
            return wartosc
        return self.tekst.from_string(wartosc).render(**ctx).strip()

    def zmienna(self, wartosc, ctx):
        if isinstance(wartosc, dict):
            return {k: self.zmienna(v, ctx) for k, v in wartosc.items()}
        if not _szablon(wartosc):
            return wartosc
        return self.natywne.from_string(wartosc).render(**ctx)


def _prawda(wartosc):
    if isinstance(wartosc, bool):
        return wartosc
    return str(wartosc).strip().lower() == "true"


def _powiadomienie(akcje, env, ctx):
    for akcja in akcje:
        if "choose" in akcja:
            for galaz in akcja["choose"]:
                warunki = galaz["conditions"]
                warunki = [warunki] if isinstance(warunki, str) else warunki
                if all(_prawda(env.tresc(w, ctx)) for w in warunki):
                    return _powiadomienie(galaz["sequence"], env, ctx)
        elif akcja.get("type") == "notify":
            return {k: env.tresc(akcja[k], ctx) for k in ("title", "message", "data")}
    return None


def uruchom(plik, trigger, dane=None, wejscia=None, stany=None):
    """Zwroc powiadomienie (dict) albo None, gdy warunki blueprintu je odrzucaja."""
    bp, _ = wczytaj(KATALOG / plik)
    domyslne = {
        nazwa: (opis or {}).get("default")
        for nazwa, opis in bp["blueprint"]["input"].items()
    }
    wejscia_ost = {**domyslne, **(wejscia or {})}
    bp = podstaw(bp, wejscia_ost)
    env = Srodowisko(stany or {})
    ctx = {"trigger": {"id": trigger, "event": {"data": dane or {}}}}
    for nazwa, wartosc in bp.get("variables", {}).items():
        ctx[nazwa] = env.zmienna(wartosc, ctx)
    for warunek in bp.get("condition", []):
        if warunek.get("condition") == "template" and not _prawda(env.tresc(warunek["value_template"], ctx)):
            return None
    return _powiadomienie(bp["action"], env, ctx)


# ---------------------------------------------------------------- struktura

@pytest.mark.parametrize("plik", PLIKI, ids=lambda p: p.name)
def test_struktura_blueprintu(plik):
    bp, uzyte = wczytaj(plik)
    opis = bp["blueprint"]
    assert opis["domain"] == "automation"
    assert opis["name"].startswith("Librus")
    assert opis["description"].strip()
    assert opis["source_url"].endswith(f"/blueprints/automation/librus_apix/{plik.name}")
    assert opis["homeassistant"]["min_version"]
    assert bp["trigger"] and bp["action"]
    wejscia = opis["input"]
    for nazwa, definicja in wejscia.items():
        assert definicja["name"], nazwa
        assert "selector" in definicja, nazwa
    assert set(uzyte) <= set(wejscia), f"!input bez definicji: {set(uzyte) - set(wejscia)}"
    assert set(wejscia) <= set(uzyte), f"nieuzyte wejscia: {set(wejscia) - set(uzyte)}"
    assert "telefon" in wejscia


def test_triggery_zdarzen_maja_galaz_w_choose():
    bp, _ = wczytaj(KATALOG / "powiadomienia_zdarzenia.yaml")
    id_triggerow = {t["id"] for t in bp["trigger"]}
    galezie = set()
    for galaz in bp["action"][0]["choose"]:
        galezie.update(re.findall(r"trigger\.id == '(\w+)'", galaz["conditions"]))
    assert id_triggerow == galezie == set(bp["variables"]["wlaczone"])


# ---------------------------------------------------------------- powiadomienia_zdarzenia

PLIK_ZDARZEN = "powiadomienia_zdarzenia.yaml"
PAYLOADY = {
    "ocena": {
        "przedmiot": "Matematyka", "ocena": "5", "data": "2026-10-01", "kategoria": "Sprawdzian",
        "nauczyciel": "Jan Kowalski", "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "wiadomosc": {
        "nadawca": "Anna Nowak", "temat": "Wycieczka", "data": "2026-10-01",
        "ma_zalacznik": True, "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "nieobecnosc": {
        "data": "2026-10-02", "przedmiot": "Fizyka", "numer_lekcji": 3, "typ": "Nieobecność",
        "usprawiedliwiona": False, "nauczyciel": "Jan Kowalski", "temat": "Ruch",
        "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "uwaga": {
        "tresc": "Rozmowa na lekcji", "data": "2026-10-03", "nauczyciel": "Anna Nowak",
        "typ": "uwaga", "rodzaj": "Negatywna", "kategoria": "Zachowanie",
        "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "zadanie": {
        "przedmiot": "Polski", "kategoria": "Praca domowa", "termin": "2026-10-05",
        "nauczyciel": "Anna Nowak", "id": "z1", "termin_iso": "2026-10-05", "dni_do": 2,
        "pilnosc": "wkrotce", "tresc": "Zad. 5 str. 12", "dzien_tygodnia_terminu": "poniedziałek",
        "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "zdarzenie": {
        "data": "2026-10-06", "tytul": "Sprawdzian", "przedmiot": "Historia", "godzina": "08:00",
        "typ": "sprawdzian", "wazne": True, "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "ogloszenie": {
        "id": "a1b2", "tytul": "Zebranie z rodzicami", "autor": "Anna Nowak", "data": "2026-10-15",
        "tresc": "Zapraszamy w czwartek o 17:00.", "wersja": 1, "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "ogloszenie_zmienione": {
        "id": "a1b2", "tytul": "Zebranie z rodzicami", "autor": "Anna Nowak", "data": "2026-10-15",
        "tresc": "Zapraszamy w czwartek o 18:00.", "wersja": 2, "poprzednia_tresc": "o 17:00",
        "uczen": "Ola Kowalska", "entry_id": "abc",
    },
    "ogloszenie_usuniete": {
        "id": "a1b2", "tytul": "Zebranie z rodzicami", "autor": "Anna Nowak", "data": "2026-10-15",
        "tresc": "Zapraszamy w czwartek o 18:00.", "wersja": 2, "uczen": "Ola Kowalska", "entry_id": "abc",
    },
}
WLACZNIKI = {
    "ocena": "wlacz_oceny", "wiadomosc": "wlacz_wiadomosci", "nieobecnosc": "wlacz_nieobecnosci",
    "uwaga": "wlacz_uwagi", "zadanie": "wlacz_zadania", "zdarzenie": "wlacz_terminarz",
    "ogloszenie": "wlacz_ogloszenia", "ogloszenie_zmienione": "wlacz_zmiany_ogloszen",
    "ogloszenie_usuniete": "wlacz_zmiany_ogloszen",
}


@pytest.mark.parametrize("trigger", PAYLOADY)
def test_domyslnie_kazde_zdarzenie_daje_powiadomienie(trigger):
    wynik = uruchom(PLIK_ZDARZEN, trigger, PAYLOADY[trigger])
    assert wynik is not None
    assert wynik["title"].strip() and wynik["message"].strip()
    assert "Ola Kowalska" in wynik["title"]
    assert wynik["data"]["group"] == "librus"
    assert wynik["data"]["tag"].startswith("librus_")


@pytest.mark.parametrize("trigger", PAYLOADY)
def test_pola_payloadu_istnieja_w_integracji(trigger):
    zrodlo = SENSOR_PY.read_text(encoding="utf-8")
    for pole in PAYLOADY[trigger]:
        assert f'"{pole}"' in zrodlo, f"pole {pole} nie wystepuje w sensor.py"


@pytest.mark.parametrize("trigger", PAYLOADY)
def test_wylaczony_typ_nie_wysyla(trigger):
    assert uruchom(PLIK_ZDARZEN, trigger, PAYLOADY[trigger], {WLACZNIKI[trigger]: False}) is None


def test_filtr_dziecka():
    dane = PAYLOADY["ocena"]
    assert uruchom(PLIK_ZDARZEN, "ocena", dane, {"dziecko": "Ola Kowalska"}) is not None
    assert uruchom(PLIK_ZDARZEN, "ocena", dane, {"dziecko": "  Ola Kowalska "}) is not None
    assert uruchom(PLIK_ZDARZEN, "ocena", dane, {"dziecko": "Jan Kowalski"}) is None


def test_brak_imienia_nie_zostawia_dwukropka_na_poczatku():
    dane = {**PAYLOADY["ocena"], "uczen": ""}
    wynik = uruchom(PLIK_ZDARZEN, "ocena", dane)
    assert wynik["title"] == "🎓 5"


def test_terminarz_tylko_wazne():
    zwykle = {**PAYLOADY["zdarzenie"], "wazne": False, "typ": "inne"}
    assert uruchom(PLIK_ZDARZEN, "zdarzenie", zwykle) is None
    assert uruchom(PLIK_ZDARZEN, "zdarzenie", zwykle, {"tylko_wazne_terminarz": False}) is not None


def test_pochwala_ma_inne_emoji_i_tytul():
    dane = {**PAYLOADY["uwaga"], "typ": "pochwala"}
    assert uruchom(PLIK_ZDARZEN, "uwaga", dane)["title"].startswith("👏")
    assert "pochwała" in uruchom(PLIK_ZDARZEN, "uwaga", dane)["title"]
    assert uruchom(PLIK_ZDARZEN, "uwaga", PAYLOADY["uwaga"])["title"].startswith("⚠️")


def test_nieobecnosc_usprawiedliwiona():
    dane = {**PAYLOADY["nieobecnosc"], "usprawiedliwiona": True}
    assert "(usprawiedliwiona)" in uruchom(PLIK_ZDARZEN, "nieobecnosc", dane)["message"]
    assert "(nieusprawiedliwiona)" in uruchom(PLIK_ZDARZEN, "nieobecnosc", PAYLOADY["nieobecnosc"])["message"]


def test_zadanie_bez_tresci_i_zdarzenie_bez_godziny():
    zadanie = {**PAYLOADY["zadanie"], "tresc": None}
    assert uruchom(PLIK_ZDARZEN, "zadanie", zadanie)["message"] == "Praca domowa, termin: 2026-10-05"
    zdarzenie = {**PAYLOADY["zdarzenie"], "godzina": ""}
    assert uruchom(PLIK_ZDARZEN, "zdarzenie", zdarzenie)["message"] == "2026-10-06, Historia"


@pytest.mark.parametrize(
    "ocena, przechodzi",
    [("1", True), ("1-", True), ("2+", True), ("3", True), ("3+", False), ("4", False), ("5", False), ("np", False)],
)
def test_prog_oceny(ocena, przechodzi):
    dane = {**PAYLOADY["ocena"], "ocena": ocena}
    wynik = uruchom(PLIK_ZDARZEN, "ocena", dane, {"prog_oceny": 3})
    assert (wynik is not None) is przechodzi


def test_prog_zero_przepuszcza_wszystko_takze_nieliczbowe():
    for ocena in ("5", "np", "+"):
        dane = {**PAYLOADY["ocena"], "ocena": ocena}
        assert uruchom(PLIK_ZDARZEN, "ocena", dane, {"prog_oceny": 0}) is not None


def test_prog_oceny_nie_dotyczy_innych_zdarzen():
    assert uruchom(PLIK_ZDARZEN, "uwaga", PAYLOADY["uwaga"], {"prog_oceny": 3}) is not None


# ---------------------------------------------------------------- wieczorny_plecak

PLECAK = "wieczorny_plecak.yaml"
PLAN = "sensor.librus_ola_plan_jutro"
RZECZY = "sensor.librus_ola_do_zrobienia_jutro"


def _stany_plecaka(wolne=False, przedmioty=("Matematyka", "Polski"), zadania=(), sprawdziany=()):
    return {
        PLAN: {"dzien_wolny": wolne},
        RZECZY: {
            "przedmioty_do_spakowania": list(przedmioty),
            "zadania": list(zadania),
            "sprawdziany": list(sprawdziany),
        },
    }


def _wejscia_plecaka(**reszta):
    return {"plan_jutro": PLAN, "do_zrobienia": RZECZY, **reszta}


def test_plecak_tresc():
    stany = _stany_plecaka(
        zadania=[
            {"przedmiot": "Matematyka", "tresc": "Zad. 3", "kategoria": "Praca domowa"},
            {"przedmiot": "Polski", "tresc": None, "kategoria": "Praca domowa"},
        ],
        sprawdziany=[{"przedmiot": "Historia", "tytul": "Sprawdzian: rozdział 2"}],
    )
    wynik = uruchom(PLECAK, "time", wejscia=_wejscia_plecaka(), stany=stany)
    assert wynik["title"] == "🎒 Plecak na jutro"
    assert wynik["message"].splitlines() == [
        "Przedmioty: Matematyka, Polski",
        "🏠 Matematyka: Zad. 3",
        "🏠 Polski",
        "📝 Historia: Sprawdzian: rozdział 2",
    ]


def test_plecak_dzien_wolny_nic_nie_wysyla():
    assert uruchom(PLECAK, "time", wejscia=_wejscia_plecaka(), stany=_stany_plecaka(wolne=True)) is None


def test_plecak_pusto():
    stany = _stany_plecaka(przedmioty=())
    assert uruchom(PLECAK, "time", wejscia=_wejscia_plecaka(), stany=stany) is None
    wynik = uruchom(PLECAK, "time", wejscia=_wejscia_plecaka(pomin_gdy_pusto=False), stany=stany)
    assert wynik is not None


def test_plecak_sensor_bez_atrybutow_nie_wywala_szablonu():
    wynik = uruchom(PLECAK, "time", wejscia=_wejscia_plecaka(pomin_gdy_pusto=False), stany={PLAN: {}, RZECZY: {}})
    assert wynik is not None and wynik["message"] == ""


# ---------------------------------------------------------------- dzien_przed_sprawdzianem

SPRAWDZIAN = "dzien_przed_sprawdzianem.yaml"
TERMINARZ = "sensor.terminarz"
SPRAWDZIANY = [
    {"data": "2026-10-20", "typ": "sprawdzian", "przedmiot": "Matematyka", "tytul": "Sprawdzian: ułamki", "dni_do": 1},
    {"data": "2026-10-20", "typ": "kartkowka", "przedmiot": "Fizyka", "tytul": "Fizyka", "dni_do": 1},
    {"data": "2026-10-22", "typ": "sprawdzian", "przedmiot": "Historia", "tytul": "Sprawdzian", "dni_do": 3},
]


def _terminarz():
    return {TERMINARZ: {"sprawdziany_7_dni": SPRAWDZIANY}}


def test_sprawdzian_jutro_wymienia_wszystkie_z_tego_dnia():
    wynik = uruchom(SPRAWDZIAN, "time", wejscia={"terminarz": TERMINARZ}, stany=_terminarz())
    assert wynik["title"] == "📝 Jutro sprawdzian"
    assert wynik["message"].splitlines() == [
        "Matematyka: Sprawdzian: ułamki (2026-10-20)",
        "Fizyka (2026-10-20)",
    ]


def test_sprawdzian_za_kilka_dni_znajduje_nie_tylko_najblizszy():
    wynik = uruchom(SPRAWDZIAN, "time", wejscia={"terminarz": TERMINARZ, "dni_wczesniej": 3.0}, stany=_terminarz())
    assert wynik["title"] == "📝 Sprawdzian za 3 dni"
    assert wynik["message"] == "Historia: Sprawdzian (2026-10-22)"


def test_sprawdzian_brak_w_danym_dniu_lub_w_ogole():
    assert uruchom(SPRAWDZIAN, "time", wejscia={"terminarz": TERMINARZ, "dni_wczesniej": 2}, stany=_terminarz()) is None
    assert uruchom(SPRAWDZIAN, "time", wejscia={"terminarz": TERMINARZ}, stany={TERMINARZ: {}}) is None


def test_sprawdzian_dzis():
    stany = {TERMINARZ: {"sprawdziany_7_dni": [{**SPRAWDZIANY[0], "dni_do": 0}]}}
    wynik = uruchom(SPRAWDZIAN, "time", wejscia={"terminarz": TERMINARZ, "dni_wczesniej": 0}, stany=stany)
    assert wynik["title"] == "📝 Sprawdzian dziś"


# ---------------------------------------------------------------- zmiany_w_planie

ZMIANY = "zmiany_w_planie.yaml"
PLAN_DZIS = "sensor.librus_ola_plan_dzis"


def _lekcja(numer, przedmiot, odwolana=False, zastepstwo=False, info=""):
    return {"numer": numer, "przedmiot": przedmiot, "odwolana": odwolana, "zastepstwo": zastepstwo, "info": info}


LEKCJE = [
    _lekcja(1, "Matematyka"),
    _lekcja(2, "Fizyka", odwolana=True, info="Odwołane"),
    _lekcja(3, "Chemia", zastepstwo=True, info="Zastępstwo: Jan Nowak"),
    _lekcja(4, ""),
    _lekcja(5, "WF", odwolana=True, zastepstwo=True),
]


def test_zmiany_w_planie_tresc():
    wynik = uruchom(ZMIANY, "time", wejscia={"plan_dzis": PLAN_DZIS}, stany={PLAN_DZIS: {"lekcje": LEKCJE}})
    assert wynik["title"] == "🏫 Zmiany w planie na dziś"
    assert wynik["message"].splitlines() == [
        "❌ 2. Fizyka – odwołana",
        "❌ 5. WF – odwołana",
        "⚠️ 3. Chemia – zastępstwo (Zastępstwo: Jan Nowak)",
    ]


def test_zmiany_w_planie_przelaczniki():
    stany = {PLAN_DZIS: {"lekcje": LEKCJE}}
    bez_odwolanych = uruchom(ZMIANY, "time", wejscia={"plan_dzis": PLAN_DZIS, "odwolane": False}, stany=stany)
    assert bez_odwolanych["message"].startswith("⚠️ 3. Chemia")
    bez_zastepstw = uruchom(ZMIANY, "time", wejscia={"plan_dzis": PLAN_DZIS, "zastepstwa": False}, stany=stany)
    assert "zastępstwo" not in bez_zastepstw["message"]


def test_zmiany_w_planie_cisza_bez_zmian():
    stany = {PLAN_DZIS: {"lekcje": [_lekcja(1, "Matematyka"), _lekcja(2, "Polski")]}}
    assert uruchom(ZMIANY, "time", wejscia={"plan_dzis": PLAN_DZIS}, stany=stany) is None
    assert uruchom(ZMIANY, "time", wejscia={"plan_dzis": PLAN_DZIS}, stany={PLAN_DZIS: {}}) is None


def test_ogloszenia_tresc_i_tag_per_ogloszenie():
    nowe = uruchom(PLIK_ZDARZEN, "ogloszenie", PAYLOADY["ogloszenie"])
    assert nowe["title"] == "📢 Ola Kowalska: Zebranie z rodzicami"
    assert nowe["message"] == "Anna Nowak: Zapraszamy w czwartek o 17:00."
    assert nowe["data"]["tag"] == "librus_ogloszenie_a1b2"
    us = uruchom(PLIK_ZDARZEN, "ogloszenie_usuniete", PAYLOADY["ogloszenie_usuniete"])
    assert "usunięte" in us["title"] and "archiwum HA" in us["message"]
    zm = uruchom(PLIK_ZDARZEN, "ogloszenie_zmienione", PAYLOADY["ogloszenie_zmienione"])
    assert "wersja 2" in zm["message"]


def test_dluga_tresc_ogloszenia_jest_przycinana():
    dlugie = {**PAYLOADY["ogloszenie"], "tresc": "słowo " * 200}
    assert len(uruchom(PLIK_ZDARZEN, "ogloszenie", dlugie)["message"]) < 300
