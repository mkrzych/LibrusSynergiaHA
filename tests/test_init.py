"""Test the Librus APIX integration."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from unittest.mock import AsyncMock, patch, MagicMock

from custom_components.librus_apix.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Librus",
        data={"username": "test_user", "password": "test_password"},
        source="user",
        entry_id="test_entry_id"
    )


@pytest.fixture
def mock_librus_client():
    """Return a mock Librus client."""
    client = MagicMock()
    client.async_authenticate = AsyncMock(return_value=True)
    client.async_get_grades = AsyncMock(return_value=[
        {
            'subject': 'Mathematyka',
            'grade': '5',
            'date': '2025-01-01',
            'category': 'Test',
            'teacher': 'Jan Kowalski',
            'type': 'numeric'
        }
    ])
    client.async_get_messages = AsyncMock(return_value=[])
    client.async_get_student_information = AsyncMock(return_value=None)
    client.async_get_homework = AsyncMock(return_value=[])
    client.async_get_homework_detail = AsyncMock(return_value=None)
    client.async_get_schedule = AsyncMock(return_value=[])
    client.async_get_timetable = AsyncMock(
        return_value={"dni": {}, "godziny": {}, "braki": []}
    )
    return client


async def test_setup_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test the setup entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is True


async def test_unload_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test unloading an entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        # Setup first
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        
        # Then unload
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result is True

async def test_event_payload_has_uczen_and_entry_id(hass: HomeAssistant):
    """Zdarzenia zawieraja uczen i entry_id."""
    from custom_components.librus_apix.sensor import LibrusDataUpdateCoordinator

    coordinator = LibrusDataUpdateCoordinator(hass, MagicMock(), "entry_1")
    student = MagicMock()
    student.name = "Ola Kowalska"
    base = coordinator._event_base(student)
    assert base == {"uczen": "Ola Kowalska", "entry_id": "entry_1"}

    fired = []
    hass.bus.async_listen("librus_apix_nowa_ocena", lambda e: fired.append(e.data))
    coordinator._fire_events(
        [],
        [{"subject": "Mat", "grade": "5", "date": "2025-01-01", "category": "k", "teacher": "t"}],
        base,
    )
    await hass.async_block_till_done()
    assert fired and fired[0]["uczen"] == "Ola Kowalska"
    assert fired[0]["entry_id"] == "entry_1"
    assert fired[0]["przedmiot"] == "Mat"


async def test_event_base_without_student(hass: HomeAssistant):
    """Brak student_info -> pusty uczen."""
    from custom_components.librus_apix.sensor import LibrusDataUpdateCoordinator

    coordinator = LibrusDataUpdateCoordinator(hass, MagicMock(), "e")
    assert coordinator._event_base(None) == {"uczen": "", "entry_id": "e"}


async def test_config_flow_duplicate_login_aborts(hass: HomeAssistant):
    """Ten sam login nie moze byc dodany dwa razy."""
    from homeassistant import config_entries

    creds = {"username": "Jan", "password": "x"}
    with patch(
        "custom_components.librus_apix.config_flow.validate_input",
        AsyncMock(return_value={"title": "Librus APIX (Jan)"}),
    ), patch("custom_components.librus_apix.async_setup_entry", AsyncMock(return_value=True)):
        r1 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r1 = await hass.config_entries.flow.async_configure(r1["flow_id"], creds)
        assert r1["type"] == "create_entry"
        r2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r2 = await hass.config_entries.flow.async_configure(r2["flow_id"], {"username": "jan ", "password": "y"})
        assert r2["type"] == "abort"
        assert r2["reason"] == "already_configured"
