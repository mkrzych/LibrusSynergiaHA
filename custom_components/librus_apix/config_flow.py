"""Config flow for Librus APIX integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BlednyLogin(Exception):
    """Librus odrzucil login lub haslo."""


class BrakDostepu(Exception):
    """Login przyjety, ale Synergia nie wpuszcza sesji (2FA, regulamin, zmiana hasla)."""


async def validate_input(hass: HomeAssistant, data: dict):
    """Zaloguj sie i sprawdz, czy strony Synergii sa dostepne (samo get_token tego nie gwarantuje)."""
    from librus_apix.exceptions import AuthorizationError

    from . import BrakDostepuSynergii, zaloguj

    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    try:
        await hass.async_add_executor_job(zaloguj, username, password)
    except BrakDostepuSynergii as ex:
        _LOGGER.error("Authentication error: %s", ex)
        raise BrakDostepu from ex
    except AuthorizationError as ex:
        _LOGGER.error("Authentication error: %s", ex)
        raise BlednyLogin from ex
    except Exception as ex:
        _LOGGER.error("Authentication error: %s", ex)
        raise ValueError("Cannot connect") from ex

    return {"title": f"Librus APIX ({username})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Librus APIX."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except BrakDostepu:
                errors["base"] = "brak_dostepu"
            except BlednyLogin:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors
        )