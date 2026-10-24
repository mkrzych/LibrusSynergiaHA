"""Archiwum ogloszen szkolnych (czyste funkcje, bez zaleznosci od Home Assistant i librus_apix).

Archiwum tylko rosnie: wpisy nigdy nie sa usuwane, zmiana tresci dopisuje nowa wersje,
a ogloszenie, ktore zniknelo z Librusa, dostaje znacznik `usuniete_z_librusa`.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# Ile kolejnych udanych pobran bez ogloszenia potrzeba, by uznac je za usuniete z Librusa
BRAKI_DO_USUNIECIA = 2

_ETYKIETY = {
    "dodał": "autor",
    "dodal": "autor",
    "autor": "autor",
    "data publikacji": "data",
    "data": "data",
    "treść": "tresc",
    "tresc": "tresc",
}


class BrakDostepu(Exception):
    """Strona zwrocila 'Brak dostepu' (wygasla sesja)."""


class NieznanyUklad(Exception):
    """Strona nie ma ani tabel ogloszen, ani komunikatu o ich braku."""


def _tekst(el: Any) -> str:
    return " ".join(el.get_text(" ", strip=True).split())


def _tresc(td: Any) -> str:
    """Tresc z zachowaniem podzialu na linie (<br> i akapity); spacje w liniach znormalizowane."""
    for br in td.find_all("br"):
        br.replace_with("\n")
    for p in td.find_all(["p", "div", "li"]):
        p.insert_after("\n")
    linie = [" ".join(l.split()) for l in td.get_text().split("\n")]
    wynik: List[str] = []
    for linia in linie:
        if linia or (wynik and wynik[-1]):  # najwyzej jedna pusta linia z rzedu
            wynik.append(linia)
    return "\n".join(wynik).strip()


def oblicz_id(tytul: str, autor: str, data: str, n: int = 0) -> str:
    """Stabilny identyfikator bez tresci - edycja tresci nie tworzy nowego ogloszenia."""
    podstawa = "|".join((tytul, autor, data)) + (f"|{n}" if n else "")
    return hashlib.sha1(podstawa.encode("utf-8")).hexdigest()[:16]


def parsuj_ogloszenia(html: str) -> List[Dict[str, str]]:
    """Wyciagnij ogloszenia ze strony /ogloszenia (kolejnosc jak w Librusie)."""
    soup = BeautifulSoup(html or "", "lxml")
    naglowek = soup.select_one("h2.inside")
    if naglowek and "Brak dostępu" in naglowek.get_text():
        raise BrakDostepu("Brak dostepu do strony ogloszen")

    tabele = soup.select("table.decorated")
    if not tabele:
        # Brak ogloszen: czerwony komunikat albo sam naglowek strony
        if soup.select_one("div.container.border-red"):
            return []
        if naglowek and "ogłoszenia" in naglowek.get_text().strip().lower():
            return []
        raise NieznanyUklad("Nie znaleziono tabel ogloszen")

    wynik: List[Dict[str, str]] = []
    uzyte: Dict[Tuple[str, str, str], int] = {}
    for tabela in tabele:
        tytul_el = tabela.select_one("thead td") or tabela.select_one("thead th")
        pola: Dict[str, str] = {"tytul": _tekst(tytul_el) if tytul_el else ""}
        bez_etykiety: List[Any] = []
        for tr in tabela.select("tbody tr") or tabela.find_all("tr"):
            if tr.find_parent("thead") is not None:
                continue
            td = tr.find("td")
            if td is None:
                continue
            th = tr.find("th")
            klucz = _ETYKIETY.get(_tekst(th).rstrip(":").lower()) if th else None
            if klucz:
                pola[klucz] = _tresc(td) if klucz == "tresc" else _tekst(td)
            else:
                bez_etykiety.append(td)
        # Uklad bez etykiet: kolejno autor, data, tresc (jak w librus_apix)
        for klucz, td in zip(("autor", "data", "tresc"), bez_etykiety):
            if klucz not in pola:
                pola[klucz] = _tresc(td) if klucz == "tresc" else _tekst(td)
        tytul, autor, data = pola["tytul"], pola.get("autor", ""), pola.get("data", "")
        if not (tytul or pola.get("tresc")):
            continue
        n = uzyte.get((tytul, autor, data), 0)
        uzyte[(tytul, autor, data)] = n + 1
        wynik.append({
            "id": oblicz_id(tytul, autor, data, n),
            "tytul": tytul,
            "autor": autor,
            "data": data,
            "tresc": pola.get("tresc", ""),
        })
    return wynik


def scal_archiwum(
    archiwum: Dict[str, Dict[str, Any]],
    pobrane: Optional[List[Dict[str, str]]],
    teraz: str,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    """Dopisz pobrane ogloszenia do archiwum; zwraca (nowe archiwum, zmiany).

    `pobrane` = None oznacza nieudane pobranie - archiwum zostaje bez zmian.
    Zmiany: listy id w kluczach nowe / zmienione / usuniete / przywrocone.
    """
    zmiany: Dict[str, List[str]] = {
        "nowe": [], "zmienione": [], "usuniete": [], "przywrocone": []
    }
    if pobrane is None:
        return archiwum, zmiany

    wynik = copy.deepcopy(archiwum)
    widoczne = set()
    for og in pobrane:
        oid = og["id"]
        widoczne.add(oid)
        wpis = wynik.get(oid)
        if wpis is None:
            wynik[oid] = {
                "id": oid,
                "tytul": og["tytul"],
                "autor": og["autor"],
                "data": og["data"],
                "pierwszy_raz": teraz,
                "ostatnio_widziane": teraz,
                "usuniete_z_librusa": None,
                "brak_kolejno": 0,
                "wersje": [{"tresc": og["tresc"], "pobrano_pierwszy": teraz, "pobrano_ostatni": teraz}],
            }
            zmiany["nowe"].append(oid)
            continue
        wpis["ostatnio_widziane"] = teraz
        wpis["brak_kolejno"] = 0
        if wpis.get("usuniete_z_librusa"):
            wpis["usuniete_z_librusa"] = None
            zmiany["przywrocone"].append(oid)
        ostatnia = wpis["wersje"][-1]
        if ostatnia["tresc"] == og["tresc"]:
            ostatnia["pobrano_ostatni"] = teraz
        else:
            wpis["wersje"].append(
                {"tresc": og["tresc"], "pobrano_pierwszy": teraz, "pobrano_ostatni": teraz}
            )
            zmiany["zmienione"].append(oid)

    for oid, wpis in wynik.items():
        if oid in widoczne or wpis.get("usuniete_z_librusa"):
            continue
        wpis["brak_kolejno"] = wpis.get("brak_kolejno", 0) + 1
        if wpis["brak_kolejno"] >= BRAKI_DO_USUNIECIA:
            wpis["usuniete_z_librusa"] = teraz
            zmiany["usuniete"].append(oid)
    return wynik, zmiany


def posortowane(archiwum: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Wpisy od najnowszych (data publikacji, potem moment pierwszego pobrania)."""
    return sorted(
        archiwum.values(),
        key=lambda w: (w.get("data") or "", w.get("pierwszy_raz") or ""),
        reverse=True,
    )


def dla_uslugi(wpis: Dict[str, Any]) -> Dict[str, Any]:
    """Wpis archiwum w postaci dla uslugi/karty (bez pol technicznych)."""
    return {
        "id": wpis["id"],
        "tytul": wpis["tytul"],
        "autor": wpis["autor"],
        "data": wpis["data"],
        "tresc": wpis["wersje"][-1]["tresc"],
        "pierwszy_raz": wpis["pierwszy_raz"],
        "ostatnio_widziane": wpis["ostatnio_widziane"],
        "usuniete_z_librusa": wpis.get("usuniete_z_librusa"),
        "wersje": copy.deepcopy(wpis["wersje"]),
    }


def podsumowanie(archiwum: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    wpisy = list(archiwum.values())
    return {
        "aktywne": sum(1 for w in wpisy if not w.get("usuniete_z_librusa")),
        "usuniete_z_librusa": sum(1 for w in wpisy if w.get("usuniete_z_librusa")),
        "edytowane": sum(1 for w in wpisy if len(w["wersje"]) > 1),
    }
