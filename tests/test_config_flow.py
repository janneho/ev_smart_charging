"""Test ev_smart_charging config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
import pytest

from custom_components.ev_smart_charging.const import (
    DOMAIN,
)

from .const import MOCK_CONFIG_CHARGER, MOCK_CONFIG_CHARGER_EXTRA, MOCK_CONFIG_USER


# This fixture bypasses the actual setup of the integration
# since we only want to test the config flow. We test the
# actual functionality of the integration in other test modules.
@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.ev_smart_charging.async_setup",
        return_value=True,
    ), patch(
        "custom_components.ev_smart_charging.async_setup_entry",
        return_value=True,
    ):
        yield


# Here we simiulate a successful config flow from the backend.
# Note that we use the `bypass_get_data` fixture here because
# we want the config flow validation to succeed during the test.
# pylint: disable=unused-argument
async def test_successful_config_flow(hass, bypass_validate_step_user):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_USER
    )

    # Check that the config flow is complete and a new entry is created with
    # the input data
    #    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "charger"

    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "charger"}
    )
    print(str(result))

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "charger"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_CHARGER
    )
    print(str(result))

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "EV Smart Charging"
    assert result["data"] == MOCK_CONFIG_CHARGER_EXTRA
    assert result["result"]
