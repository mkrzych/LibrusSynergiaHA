"""Testy parsera i archiwum ogloszen szkolnych (strona /ogloszenia)."""

import pytest

from _pure import load

og = load("ogloszenia")

T1, T2, T3, T4 = (f"2026-10-2{i}T10:00:00+02:00" for i in range(1, 5))


def _html():
    from _builders import FIXTURES
    return (FIXTURES / "ogloszenia.html").read_text(encoding="utf-8")


def _og(tytul="Zebranie", tresc="Treść", autor="Kowalska Anna", data="2026-10-15"):
    return {"id": og.oblicz_id(tytul, autor, data), "tytul": tytul, "autor": autor, "data": data, "tresc": tresc}


# ------------------------------------------------------------------ parser

def test_parsuje_ogloszenia_z_etykietami_i_zachowuje_linie():
    wpisy = og.parsuj_ogloszenia(_html())
    assert [w["tytul"] for w in wpisy] == ["Zebranie z rodzicami klas 5", "Dzień otwarty"]
    z = wpisy[0]
    assert z["autor"] == "Kowalska Anna" and z["data"] == "2026-10-15"
    assert z["tresc"] == "Szanowni Państwo,\nzapraszamy na zebranie w czwartek o 17:00.\n\nSala 12."
    assert wpisy[1]["tresc"] == "Pierwszy akapit.\nDrugi akapit."
    assert z["id"] == og.oblicz_id("Zebranie z rodzicami klas 5", "Kowalska Anna", "2026-10-15")


def test_uklad_bez_etykiet_jak_w_librus_apix():
    html = ('<table class="decorated"><thead><tr><td>Tytul</td></tr></thead><tbody>'
            '<tr class="line0"><td>Autor X</td></tr><tr class="line1"><td>2026-01-02</td></tr>'
            '<tr class="line0"><td>Tresc</td></tr></tbody></table>')
    assert og.parsuj_ogloszenia(html) == [_og("Tytul", "Tresc", "Autor X", "2026-01-02")]


def test_identyczne_ogloszenia_dostaja_rozne_id():
    tab = ('<table class="decorated"><thead><tr><td>A</td></tr></thead><tbody>'
           '<tr><th>Dodał</th><td>X</td></tr><tr><th>Data publikacji</th><td>2026-01-02</td></tr>'
           '<tr><th>Treść</th><td>t</td></tr></tbody></table>')
    ids = [w["id"] for w in og.parsuj_ogloszenia(tab * 2)]
    assert len(set(ids)) == 2


def test_brak_ogloszen_brak_dostepu_i_nieznany_uklad():
    assert og.parsuj_ogloszenia(
        '<div class="container border-red resizeable center"><div><p>Brak ogłoszeń</p></div></div>'
    ) == []
    with pytest.raises(og.BrakDostepu):
        og.parsuj_ogloszenia('<h2 class="inside">Brak dostępu</h2>')
    with pytest.raises(og.NieznanyUklad):
        og.parsuj_ogloszenia("<html><body><form>Zaloguj</form></body></html>")


def test_id_nie_zalezy_od_tresci():
    assert _og(tresc="a")["id"] == _og(tresc="b")["id"]
    assert _og(tytul="a")["id"] != _og(tytul="b")["id"]


# ------------------------------------------------------------------ archiwum

def test_nowe_ogloszenie_trafia_do_archiwum():
    arch, zm = og.scal_archiwum({}, [_og()], T1)
    w = arch[_og()["id"]]
    assert zm["nowe"] == [w["id"]]
    assert w["wersje"] == [{"tresc": "Treść", "pobrano_pierwszy": T1, "pobrano_ostatni": T1}]
    assert w["pierwszy_raz"] == T1 and w["usuniete_z_librusa"] is None


def test_bez_zmian_aktualizuje_tylko_znaczniki_czasu():
    arch, _ = og.scal_archiwum({}, [_og()], T1)
    arch2, zm = og.scal_archiwum(arch, [_og()], T2)
    w = arch2[_og()["id"]]
    assert not any(zm.values())
    assert len(w["wersje"]) == 1 and w["wersje"][0]["pobrano_ostatni"] == T2
    assert w["ostatnio_widziane"] == T2 and w["pierwszy_raz"] == T1
    assert arch[_og()["id"]]["ostatnio_widziane"] == T1  # wejscie nie jest modyfikowane


def test_edycja_tresci_dopisuje_wersje_a_stara_zostaje():
    arch, _ = og.scal_archiwum({}, [_og(tresc="Zebranie o 17")], T1)
    arch, zm = og.scal_archiwum(arch, [_og(tresc="Zebranie o 18")], T2)
    w = arch[_og()["id"]]
    assert zm["zmienione"] == [w["id"]]
    assert [v["tresc"] for v in w["wersje"]] == ["Zebranie o 17", "Zebranie o 18"]


def test_znikniecie_dopiero_po_dwoch_brakach_i_wpis_zostaje():
    arch, _ = og.scal_archiwum({}, [_og(), _og("Inne")], T1)
    arch, zm = og.scal_archiwum(arch, [_og("Inne")], T2)
    assert zm["usuniete"] == [] and arch[_og()["id"]]["usuniete_z_librusa"] is None
    arch, zm = og.scal_archiwum(arch, [_og("Inne")], T3)
    w = arch[_og()["id"]]
    assert zm["usuniete"] == [w["id"]] and w["usuniete_z_librusa"] == T3
    assert w["wersje"][0]["tresc"] == "Treść"
    arch, zm = og.scal_archiwum(arch, [_og("Inne")], T4)
    assert zm["usuniete"] == [] and arch[w["id"]]["usuniete_z_librusa"] == T3  # data pierwszego braku


def test_pusta_lista_tez_liczy_sie_jako_brak():
    arch, _ = og.scal_archiwum({}, [_og()], T1)
    arch, _ = og.scal_archiwum(arch, [], T2)
    arch, zm = og.scal_archiwum(arch, [], T3)
    assert zm["usuniete"] == [_og()["id"]] and len(arch) == 1


def test_brak_przerwany_ponownym_pojawieniem_sie_zeruje_licznik():
    arch, _ = og.scal_archiwum({}, [_og()], T1)
    arch, _ = og.scal_archiwum(arch, [], T2)
    arch, _ = og.scal_archiwum(arch, [_og()], T3)
    arch, zm = og.scal_archiwum(arch, [], T4)
    assert zm["usuniete"] == []


def test_powrot_po_usunieciu_czysci_znacznik_a_historia_zostaje():
    arch, _ = og.scal_archiwum({}, [_og()], T1)
    for t in (T2, T3):
        arch, _ = og.scal_archiwum(arch, [], t)
    arch, zm = og.scal_archiwum(arch, [_og(tresc="Nowa")], T4)
    w = arch[_og()["id"]]
    assert zm["przywrocone"] == [w["id"]] and zm["zmienione"] == [w["id"]]
    assert w["usuniete_z_librusa"] is None and len(w["wersje"]) == 2


def test_nieudane_pobranie_nic_nie_zmienia():
    arch, _ = og.scal_archiwum({}, [_og()], T1)
    for t in (T2, T3, T4):
        arch2, zm = og.scal_archiwum(arch, None, t)
        assert arch2 == arch and not any(zm.values())


def test_posortowane_dla_uslugi_i_podsumowanie():
    arch, _ = og.scal_archiwum({}, [_og("Stare", data="2026-09-01"), _og("Nowe", data="2026-10-20")], T1)
    arch, _ = og.scal_archiwum(arch, [_og("Nowe", "v2", data="2026-10-20")], T2)
    arch, _ = og.scal_archiwum(arch, [_og("Nowe", "v2", data="2026-10-20")], T3)
    lista = [og.dla_uslugi(w) for w in og.posortowane(arch)]
    assert [w["tytul"] for w in lista] == ["Nowe", "Stare"]
    assert lista[0]["tresc"] == "v2" and len(lista[0]["wersje"]) == 2
    assert "brak_kolejno" not in lista[0]
    assert lista[1]["usuniete_z_librusa"] == T3
    assert og.podsumowanie(arch) == {"aktywne": 1, "usuniete_z_librusa": 1, "edytowane": 1}
