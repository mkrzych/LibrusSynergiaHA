"""Testy parsera uwag nauczycieli (strona /uwagi)."""

import pytest

from _pure import load

uw = load("uwagi")


def _html():
    from _builders import FIXTURES
    return (FIXTURES / "uwagi.html").read_text(encoding="utf-8")


def test_parsuje_pochwale_i_uwagi_z_tabeli():
    wpisy = uw.parsuj_uwagi(_html())
    assert len(wpisy) == 4  # stopka (colspan) pominieta
    p = wpisy[0]
    assert p["typ"] == "pochwala" and p["rodzaj"] == "pozytywna"
    assert p["data"] == "2026-10-15" and p["nauczyciel"] == "Kowalska Anna" and p["kategoria"] == "Uwaga"
    assert p["tresc"].startswith("Reprezentowanie szkoły")
    assert wpisy[1]["typ"] == "uwaga"


def test_bialy_znaki_sa_normalizowane_a_duplikaty_dostaja_rozne_id():
    wpisy = uw.parsuj_uwagi(_html())
    assert wpisy[1]["tresc"] == "Rozmowa w trakcie lekcji."
    ids = [w["id"] for w in wpisy[1:]]
    assert len(set(ids)) == 3
    assert ids[0] == "2026-10-10|Nowak Jan|Rozmowa w trakcie lekcji."
    assert ids[1].endswith("|1") and ids[2].endswith("|2")


def test_podsumowanie():
    assert uw.podsumowanie(uw.parsuj_uwagi(_html())) == {"pochwaly": 1, "uwagi": 3}


def test_typ_uwagi():
    assert uw.typ_uwagi("Pozytywna") == "pochwala"
    assert uw.typ_uwagi("negatywna") == "uwaga"
    assert uw.typ_uwagi("informacja") == "informacja"


def test_uczen_bez_uwag_daje_pusta_liste():
    assert uw.parsuj_uwagi('<div class="container"><h2 class="inside">Uwagi</h2><p>Brak</p></div>') == []


def test_brak_dostepu_i_nieznany_uklad():
    with pytest.raises(uw.BrakDostepu):
        uw.parsuj_uwagi('<h2 class="inside">Brak dostępu</h2>')
    with pytest.raises(uw.NieznanyUklad):
        uw.parsuj_uwagi("<html><body><form>Zaloguj</form></body></html>")
