"""Test ev_smart_charging coordinator."""
from unittest.mock import patch
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.entity_registry import async_get as async_entity_registry_get
from homeassistant.helpers.entity_registry import EntityRegistry

from custom_components.ev_smart_charging.coordinator import (
    EVSmartChargingCoordinator,
)
from custom_components.ev_smart_charging.const import DOMAIN
from custom_components.ev_smart_charging.sensor import EVSmartChargingSensor

from tests.helpers.helpers import (
    MockChargerEntity,
    MockPriceEntity,
    MockSOCEntity,
    MockTargetSOCEntity,
)
from tests.price import PRICE_20220930, PRICE_20221001
from .const import MOCK_CONFIG_ALL, MOCK_CONFIG_NO_TARGET_SOC

# This fixture is used to prevent HomeAssistant from doing Service Calls.
@pytest.fixture(name="skip_service_calls")
def skip_service_calls_fixture():
    """Skip service calls."""
    with patch("homeassistant.core.ServiceRegistry.async_call"):
        yield


# pylint: disable=unused-argument
@pytest.mark.freeze_time("2022-09-30 14:00:00+02:00")  # 14:00 CEST time
async def test_coordinator(
    hass: HomeAssistant, skip_service_calls, set_cet_timezone, freezer
):
    """Test sensor properties."""

    entity_registry: EntityRegistry = async_entity_registry_get(hass)
    MockSOCEntity.create(hass, entity_registry, "55")
    MockTargetSOCEntity.create(hass, entity_registry, "80")
    MockPriceEntity.create(hass, entity_registry, 123)
    MockChargerEntity.create(hass, entity_registry, STATE_OFF)

    # Test default Target SOC
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_NO_TARGET_SOC, entry_id="test"
    )
    coordinator = EVSmartChargingCoordinator(hass, config_entry)
    assert coordinator is not None

    sensor: EVSmartChargingSensor = EVSmartChargingSensor(config_entry)
    assert sensor is not None
    await coordinator.add_sensor(sensor)

    assert coordinator.ev_target_soc == 100

    # Test turn on and off charging
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ALL, entry_id="test")
    coordinator = EVSmartChargingCoordinator(hass, config_entry)
    assert coordinator is not None

    sensor: EVSmartChargingSensor = EVSmartChargingSensor(config_entry)
    assert sensor is not None
    await coordinator.add_sensor(sensor)
    assert coordinator.ev_target_soc == 80

    await coordinator.turn_on_charging()
    assert coordinator.sensor.native_value == STATE_ON
    await coordinator.turn_off_charging()
    assert coordinator.sensor.native_value == STATE_OFF

    # Provide price
    new_price = 75
    new_raw_today = PRICE_20220930
    new_raw_tomorrow = PRICE_20221001
    MockPriceEntity.set_state(hass, new_price, new_raw_today, new_raw_tomorrow)
    await coordinator.update_sensors()
    await hass.async_block_till_done()
    assert coordinator.tomorrow_valid

    # Turn on switches
    await coordinator.switch_active_update(True)
    await coordinator.switch_apply_limit_update(True)
    await hass.async_block_till_done()

    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF

    # Move time to scheduled charging time
    freezer.move_to("2022-10-01 03:00:00+02:00")
    await coordinator.update_state()
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_ON
    assert coordinator.sensor.state == STATE_ON

    # Move time to after scheduled charging time
    freezer.move_to("2022-10-01 08:00:00+02:00")
    await coordinator.update_state()
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF

    # Move back time to recreate the schedule
    freezer.move_to("2022-09-30 20:00:00+02:00")
    await coordinator.update_state()
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF

    # Move time to scheduled charging time
    freezer.move_to("2022-10-01 03:00:00+02:00")
    await coordinator.update_state()
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_ON
    assert coordinator.sensor.state == STATE_ON

    # SOC reached Target SOC
    MockSOCEntity.set_state(hass, "80")
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF


# pylint: disable=unused-argument
async def test_validate_input_sensors(hass: HomeAssistant):
    """Test validate_input_sensors()"""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ALL, entry_id="test")
    coordinator = EVSmartChargingCoordinator(hass, config_entry)
    entity_registry: EntityRegistry = async_entity_registry_get(hass)

    assert coordinator.validate_input_sensors() == "Input sensors not ready."
    MockPriceEntity.create(hass, entity_registry, 123)
    assert coordinator.validate_input_sensors() == "Input sensors not ready."
    MockSOCEntity.create(hass, entity_registry, "55")
    assert coordinator.validate_input_sensors() == "Input sensors not ready."
    MockTargetSOCEntity.create(hass, entity_registry, "80")
    assert coordinator.validate_input_sensors() is None