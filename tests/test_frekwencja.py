"""Testy frekwencji: sensory i zdarzenie nowej nieobecnosci."""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

import _ha_stub  # noqa: F401
from _pure import load_full, load_package

const = load_full("const")
sensor = load_full("sensor")
pkg = load_package()

DOMAIN = const.DOMAIN
EVENT_NOWA_NIEOBECNOSC = sensor.EVENT_NOWA_NIEOBECNOSC
LibrusDataUpdateCoordinator = sensor.LibrusDataUpdateCoordinator
LibrusFrekwencjaSensor = sensor.LibrusFrekwencjaSensor
LibrusNieobecnosciSensor = sensor.LibrusNieobecnosciSensor


class _Bus:
    def __init__(self):
        self._listeners = {}
        self._pending = []

    def async_listen(self, event_type, callback):
        self._listeners.setdefault(event_type, []).append(callback)

    def fire(self, event_type, data):
        event = MagicMock()
        event.data = data
        for callback in self._listeners.get(event_type, []):
            result = callback(event)
            if inspect.isawaitable(result):
                self._pending.append(result)


@pytest.fixture
def hass():
    hass = MagicMock()
    hass.bus = _Bus()

    async def _async_block_till_done():
        if hass.bus._pending:
            await asyncio.gather(*hass.bus._pending)
            hass.bus._pending.clear()

    hass.async_block_till_done = AsyncMock(side_effect=_async_block_till_done)
    return hass


def _wpis(symbol, data, lekcja, href):
    return {
        "symbol": symbol,
        "typ": {"nb": "Nieobecność", "u": "Nieobecność uspr.", "sp": "Spóźnienie"}[symbol],
        "data": data,
        "numer_lekcji": lekcja,
        "przedmiot": "Matematyka",
        "nauczyciel": "Jan Kowalski",
        "temat": "Ułamki",
        "semestr": 1,
        "href": href,
    }


def _attendance(*wpisy):
    return {
        "wpisy": list(wpisy),
        "frekwencja": {"semestr_1": 90.0, "semestr_2": 100.0, "calosc": 92.5},
    }


def _client(attendance):
    client = MagicMock()
    client.async_get_student_information = AsyncMock(return_value=None)
    client.async_get_grades = AsyncMock(return_value=[])
    client.async_get_messages = AsyncMock(return_value=[])
    client.async_get_homework = AsyncMock(return_value=[])
    client.async_get_schedule = AsyncMock(return_value=[])
    client.async_get_timetable = AsyncMock(return_value={"dni": {}, "godziny": {}, "braki": []})
    client.async_get_attendance = AsyncMock(side_effect=attendance)
    return client


@pytest.fixture
def events(hass):
    zebrane = []
    hass.bus.async_listen(EVENT_NOWA_NIEOBECNOSC, lambda e: zebrane.append(e.data))
    return zebrane


async def test_event_tylko_dla_nowej_nieobecnosci(hass, events):
    stara = _wpis("nb", "2026-09-01", 2, "/a")
    nowa = _wpis("nb", "2026-09-02", 3, "/b")
    spoznienie = _wpis("sp", "2026-09-02", 4, "/c")
    client = _client([
        _attendance(stara),
        _attendance(stara),                    # bez zmian
        _attendance(stara, nowa, spoznienie),  # nowa nieobecnosc + spoznienie
        _attendance(stara, nowa, spoznienie),  # powtorka
    ])
    coordinator = LibrusDataUpdateCoordinator(hass, client)

    await coordinator._async_update_data()  # seed
    await coordinator._async_update_data()
    await hass.async_block_till_done()
    assert events == []

    await coordinator._async_update_data()
    await coordinator._async_update_data()
    await hass.async_block_till_done()
    assert events == [{
        "data": "2026-09-02",
        "przedmiot": "Matematyka",
        "numer_lekcji": 3,
        "typ": "Nieobecność",
        "usprawiedliwiona": False,
        "nauczyciel": "Jan Kowalski",
        "temat": "Ułamki",
    }]


async def test_usprawiedliwienie_nie_jest_nowa_nieobecnoscia(hass, events):
    client = _client([
        _attendance(_wpis("nb", "2026-09-01", 2, "/a")),
        _attendance(_wpis("u", "2026-09-01", 2, "/a")),
    ])
    coordinator = LibrusDataUpdateCoordinator(hass, client)
    await coordinator._async_update_data()
    data = await coordinator._async_update_data()
    await hass.async_block_till_done()
    assert events == []
    assert data["frekwencja"]["nieobecnosci"][0]["usprawiedliwiona"] is True


async def test_blad_pierwszego_pobrania_nie_ogasza_starych_nieobecnosci(hass, events):
    stara = _wpis("nb", "2026-09-01", 2, "/a")
    client = _client([None, _attendance(stara), _attendance(stara)])
    coordinator = LibrusDataUpdateCoordinator(hass, client)

    data = await coordinator._async_update_data()
    assert data["frekwencja"] == {"procent": {}, "nieobecnosci": []}

    await coordinator._async_update_data()  # seed przy pierwszym sukcesie
    await coordinator._async_update_data()
    await hass.async_block_till_done()
    assert events == []


async def test_blad_pobrania_zachowuje_poprzednie_dane(hass):
    client = _client([_attendance(_wpis("nb", "2026-09-01", 2, "/a")), None])
    coordinator = LibrusDataUpdateCoordinator(hass, client)
    coordinator.data = await coordinator._async_update_data()
    data = await coordinator._async_update_data()
    assert len(data["frekwencja"]["nieobecnosci"]) == 1


async def test_sensory(hass):
    client = _client([_attendance(
        _wpis("nb", "2026-09-01", 2, "/a"),
        _wpis("u", "2026-09-03", 1, "/b"),
        _wpis("sp", "2026-09-04", 1, "/c"),
    )])
    coordinator = LibrusDataUpdateCoordinator(hass, client)
    coordinator.data = await coordinator._async_update_data()
    entry = MagicMock(entry_id="eid")

    frekwencja = LibrusFrekwencjaSensor(coordinator, entry)
    assert frekwencja.native_value == 92.5
    assert frekwencja.extra_state_attributes == {"semestr_1": 90.0, "semestr_2": 100.0}

    nieobecnosci = LibrusNieobecnosciSensor(coordinator, entry)
    assert nieobecnosci.native_value == 2  # spoznienie nie liczy sie
    attrs = nieobecnosci.extra_state_attributes
    assert attrs["usprawiedliwione"] == 1
    assert attrs["nieusprawiedliwione"] == 1
    assert attrs["lista"][0]["data"] == "2026-09-03"  # najnowsze pierwsze


async def test_klient_mapuje_wpisy_biblioteki():
    """LibrusApiClient.async_get_attendance mapuje Attendance na slowniki."""
    from unittest.mock import patch

    from librus_apix.attendance import Attendance

    LibrusApiClient = pkg.LibrusApiClient

    sem1 = [Attendance("NB", "/h1", 0, "2026-09-02", "Nieobecność", "J. K.", 3, False, "T", "Mat")]
    sem2 = [Attendance("sp", "/h2", 1, "2027-02-02", "Spóźnienie", "J. K.", 1, False, "T", "Fiz")]
    client = LibrusApiClient.__new__(LibrusApiClient)
    client._client = object()
    client._token = "t"
    with patch("librus_apix.attendance.get_attendance", return_value=[sem1, sem2]), patch(
        "librus_apix.attendance.get_attendance_frequency", return_value=(0.9, 1.0, 0.925)
    ):
        wynik = await client.async_get_attendance()

    assert wynik["frekwencja"] == {"semestr_1": 90.0, "semestr_2": 100.0, "calosc": 92.5}
    assert [(w["symbol"], w["semestr"], w["numer_lekcji"]) for w in wynik["wpisy"]] == [
        ("nb", 1, 3),
        ("sp", 2, 1),
    ]
