"""Logowanie ze sprawdzeniem dostepu do Synergii, blokada ponowien i bledy setupu wpisu."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import _ha_stub
from _pure import load_full, load_package

pytestmark = pytest.mark.skipif(
    not _ha_stub.STUBBED, reason="testy z atrapami HA; prawdziwy HA ma wlasne testy"
)

pkg = load_package() if _ha_stub.STUBBED else None

from librus_apix.exceptions import AuthorizationError, MaintananceError  # noqa: E402

BRAK_DOSTEPU = '<html><body><h2 class="inside">Brak dostępu</h2></body></html>'
INFORMACJA = '<html><body><h2 class="inside">Informacje o uczniu</h2><table></table></body></html>'


def _klient_librus(html, url="https://synergia.librus.pl/informacja"):
    c = MagicMock()
    c.INFO_URL = "https://synergia.librus.pl/informacja"
    c.get_token.return_value = "token"
    c.get.return_value = SimpleNamespace(text=html, url=url)
    return c


def test_zaloguj_brak_dostepu_mimo_tokenu():
    with patch.object(pkg, "new_client", return_value=_klient_librus(BRAK_DOSTEPU)):
        with pytest.raises(pkg.BrakDostepuSynergii, match="2FA"):
            pkg.zaloguj("u", "p")


def test_zaloguj_przekierowanie_na_logowanie():
    c = _klient_librus("<html></html>", url="https://synergia.librus.pl/loguj/portalRodzina")
    with patch.object(pkg, "new_client", return_value=c):
        with pytest.raises(pkg.BrakDostepuSynergii):
            pkg.zaloguj("u", "p")


def test_zaloguj_ok_zwraca_klienta_i_token():
    c = _klient_librus(INFORMACJA)
    with patch.object(pkg, "new_client", return_value=c):
        assert pkg.zaloguj("u", "p") == (c, "token")
    c.get.assert_called_once_with(c.INFO_URL)


@pytest.mark.parametrize("blad", [pkg.BrakDostepuSynergii("x"), AuthorizationError("zle haslo")] if pkg else [])
def test_authenticate_po_odrzuceniu_nie_loguje_sie_w_kolko(blad):
    klient = pkg.LibrusApiClient("u", "p")
    zaloguj = MagicMock(side_effect=blad)
    with patch.object(pkg, "zaloguj", zaloguj):
        assert asyncio.run(klient.async_authenticate()) is False
        # kolejne metody w tym samym cyklu nie probuja juz logowania
        assert asyncio.run(klient.async_get_uwagi()) is None
        assert asyncio.run(klient.async_get_ogloszenia()) is None
    assert zaloguj.call_count == 1


def test_authenticate_blad_sieci_nie_blokuje():
    klient = pkg.LibrusApiClient("u", "p")
    zaloguj = MagicMock(side_effect=[ConnectionError("brak sieci"), (MagicMock(), "t")])
    with patch.object(pkg, "zaloguj", zaloguj):
        assert asyncio.run(klient.async_authenticate()) is False
        assert asyncio.run(klient.async_authenticate()) is True
    assert klient._token == "t"


def _hass_i_wpis():
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = SimpleNamespace(entry_id="e1", data={"username": "u", "password": "p"})
    return hass, entry


@pytest.mark.parametrize(
    "blad, oczekiwany",
    [
        (pkg.BrakDostepuSynergii("brak"), _ha_stub.ConfigEntryError),
        (AuthorizationError("zle haslo"), _ha_stub.ConfigEntryError),
        (MaintananceError("przerwa"), _ha_stub.ConfigEntryNotReady),
        (ConnectionError("siec"), _ha_stub.ConfigEntryNotReady),
    ] if pkg else [],
)
def test_setup_entry_bledy_logowania(blad, oczekiwany):
    hass, entry = _hass_i_wpis()
    with patch.object(pkg, "zaloguj", MagicMock(side_effect=blad)):
        with pytest.raises(oczekiwany):
            asyncio.run(pkg.async_setup_entry(hass, entry))
    hass.config_entries.async_forward_entry_setups.assert_not_called()


def test_setup_entry_pierwsze_odswiezenie_przed_platformami():
    hass, entry = _hass_i_wpis()
    kolejnosc = []
    koordynator = MagicMock()
    koordynator.async_config_entry_first_refresh = AsyncMock(
        side_effect=lambda: kolejnosc.append("refresh")
    )
    hass.config_entries.async_forward_entry_setups = AsyncMock(
        side_effect=lambda *a: kolejnosc.append("platformy")
    )
    sensor = load_full("sensor")
    with patch.object(pkg, "zaloguj", MagicMock(return_value=(MagicMock(), "t"))), patch.object(
        sensor, "LibrusDataUpdateCoordinator", return_value=koordynator
    ):
        assert asyncio.run(pkg.async_setup_entry(hass, entry)) is True
    assert kolejnosc == ["refresh", "platformy"]
    assert hass.data[pkg.DOMAIN]["e1"]["coordinator"] is koordynator


@pytest.mark.parametrize(
    "blad, wyjatek",
    [
        ("BrakDostepuSynergii", "BrakDostepu"),
        ("AuthorizationError", "BlednyLogin"),
        ("ConnectionError", "ValueError"),
    ],
)
def test_validate_input_rozroznia_bledy(blad, wyjatek):
    cf = load_full("config_flow")
    bledy = {
        "BrakDostepuSynergii": pkg.BrakDostepuSynergii("x"),
        "AuthorizationError": AuthorizationError("x"),
        "ConnectionError": ConnectionError("x"),
    }
    oczekiwany = getattr(cf, wyjatek, None) or ValueError
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=bledy[blad])
    with pytest.raises(oczekiwany):
        asyncio.run(cf.validate_input(hass, {"username": "u", "password": "p"}))


def test_validate_input_ok():
    cf = load_full("config_flow")
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=(MagicMock(), "t"))
    wynik = asyncio.run(cf.validate_input(hass, {"username": "13054150", "password": "p"}))
    assert wynik == {"title": "Librus APIX (13054150)"}
