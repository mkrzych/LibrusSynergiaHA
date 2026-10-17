"""Czyste funkcje uwag nauczycieli (bez zaleznosci od Home Assistant i librus_apix)."""

from __future__ import annotations

from typing import Any, Dict, List

from bs4 import BeautifulSoup

TYP_POCHWALA = "pochwala"
TYP_UWAGA = "uwaga"
TYP_INFORMACJA = "informacja"

_KOLUMNY = 5  # Uwaga | Data | Kto dodal | Rodzaj uwagi | Kategoria


class BrakDostepu(Exception):
    """Strona zwrocila 'Brak dostepu' (wygasla sesja)."""


class NieznanyUklad(Exception):
    """Strona nie ma ani tabeli uwag, ani naglowka 'Uwagi' (zmiana HTML albo ekran logowania)."""


def typ_uwagi(rodzaj: str) -> str:
    """Rodzaj z Librusa ('pozytywna' / 'negatywna') -> pochwala / uwaga / informacja."""
    r = (rodzaj or "").strip().lower()
    if r.startswith("pozytyw"):
        return TYP_POCHWALA
    if r.startswith("negatyw"):
        return TYP_UWAGA
    return TYP_INFORMACJA


def _tekst(td: Any) -> str:
    return " ".join(td.get_text(" ", strip=True).split())


def parsuj_uwagi(html: str) -> List[Dict[str, Any]]:
    """Wyciagnij uwagi ze strony /uwagi; identyczne wpisy dostaja kolejne numery w `id`."""
    soup = BeautifulSoup(html or "", "lxml")
    naglowek = soup.select_one("h2.inside")
    if naglowek and "Brak dostępu" in naglowek.get_text():
        raise BrakDostepu("Brak dostepu do strony uwag")

    tabela = soup.select_one("table.decorated")
    if tabela is None:
        # Uczen bez uwag: strona ma naglowek, ale zadnej tabeli
        if naglowek and "uwagi" in naglowek.get_text().strip().lower():
            return []
        raise NieznanyUklad("Nie znaleziono tabeli uwag")

    wynik: List[Dict[str, Any]] = []
    uzyte: Dict[str, int] = {}
    for tr in tabela.select("tbody tr"):
        komorki = tr.find_all("td", recursive=False)
        if len(komorki) < _KOLUMNY:
            continue  # pusty wiersz stopki / separator
        tresc, data, nauczyciel, rodzaj, kategoria = (_tekst(td) for td in komorki[:_KOLUMNY])
        podstawa = klucz_uwagi({"data": data, "nauczyciel": nauczyciel, "tresc": tresc})
        n = uzyte.get(podstawa, 0)
        uzyte[podstawa] = n + 1
        wynik.append({
            "id": podstawa if n == 0 else f"{podstawa}|{n}",
            "tresc": tresc,
            "data": data,
            "nauczyciel": nauczyciel,
            "rodzaj": rodzaj,
            "kategoria": kategoria,
            "typ": typ_uwagi(rodzaj),
        })
    return wynik


def klucz_uwagi(uwaga: Dict[str, Any]) -> str:
    """Podstawa klucza dedup: Librus nie podaje identyfikatora wiersza."""
    return "|".join(str(uwaga.get(k, "")) for k in ("data", "nauczyciel", "tresc"))


def podsumowanie(uwagi: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "pochwaly": sum(1 for u in uwagi if u["typ"] == TYP_POCHWALA),
        "uwagi": sum(1 for u in uwagi if u["typ"] == TYP_UWAGA),
    }
