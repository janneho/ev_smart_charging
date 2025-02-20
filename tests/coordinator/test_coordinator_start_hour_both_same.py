"""Test ev_smart_charging coordinator."""
from datetime import datetime

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.entity_registry import async_get as async_entity_registry_get
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import dt as dt_util

from custom_components.ev_smart_charging.coordinator import (
    EVSmartChargingCoordinator,
)
from custom_components.ev_smart_charging.const import DOMAIN
from custom_components.ev_smart_charging.sensor import EVSmartChargingSensorCharging

from tests.helpers.helpers import (
    MockChargerEntity,
    MockPriceEntity,
    MockSOCEntity,
    MockTargetSOCEntity,
)
from tests.price import PRICE_20221001, PRICE_20221002
from tests.coordinator.const import (
    MOCK_CONFIG_START_HOUR_3A,
    MOCK_CONFIG_START_HOUR_3B,
)


# pylint: disable=unused-argument
async def test_coordinator_start_hour_both_same_3a(
    hass: HomeAssistant, skip_service_calls, set_cet_timezone, freezer
):
    """Test Coordinator."""

    # Continuous charging

    # end == start
    # - both am
    # -- now before end, after start am, after start pm <====
    # - both pm
    # -- now before end am, before end pm, after start

    freezer.move_to("2022-10-01T02:00:00+02:00")

    entity_registry: EntityRegistry = async_entity_registry_get(hass)
    MockSOCEntity.create(hass, entity_registry, "66")
    MockTargetSOCEntity.create(hass, entity_registry, "80")
    MockPriceEntity.create(hass, entity_registry, 123)
    MockChargerEntity.create(hass, entity_registry, STATE_OFF)
    MockPriceEntity.set_state(hass, PRICE_20221001, None)
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_START_HOUR_3A, entry_id="test"
    )
    coordinator = EVSmartChargingCoordinator(hass, config_entry)
    assert coordinator is not None
    sensor: EVSmartChargingSensorCharging = EVSmartChargingSensorCharging(config_entry)
    assert sensor is not None
    await coordinator.add_sensor([sensor])
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await coordinator.switch_apply_limit_update(False)
    await coordinator.switch_continuous_update(True)
    await coordinator.switch_ev_connected_update(True)
    await coordinator.switch_keep_on_update(False)
    await hass.async_block_till_done()

    # Start_hour = 10:00, Ready_hour = 10:00
    # 5 hours => 03:00-08:00
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF
    assert coordinator.sensor.charging_is_planned is True
    assert coordinator.sensor.charging_start_time == datetime(
        2022, 10, 1, 3, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_stop_time == datetime(
        2022, 10, 1, 8, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_number_of_hours == 5

    # Start_hour = 10:00, Ready_hour = 10:00
    # 5 hours => None
    freezer.move_to("2022-10-01T11:00:00+02:00")
    MockSOCEntity.set_state(hass, "67")
    await coordinator.switch_active_update(False)
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF
    assert coordinator.sensor.charging_is_planned is False
    assert coordinator.sensor.charging_start_time is None
    assert coordinator.sensor.charging_stop_time is None
    assert coordinator.sensor.charging_number_of_hours == 0

    # Start_hour = 10:00, Ready_hour = 10:00
    # 5 hours => 03:00-=8:00
    freezer.move_to("2022-10-01T14:00:00+02:00")
    MockPriceEntity.set_state(hass, PRICE_20221001, PRICE_20221002)
    MockSOCEntity.set_state(hass, "66")
    await coordinator.switch_active_update(False)
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF
    assert coordinator.sensor.charging_is_planned is True
    assert coordinator.sensor.charging_start_time == datetime(
        2022, 10, 2, 3, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_stop_time == datetime(
        2022, 10, 2, 8, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_number_of_hours == 5


async def test_coordinator_start_hour_both_same_3b(
    hass: HomeAssistant, skip_service_calls, set_cet_timezone, freezer
):
    """Test Coordinator."""

    # Continuous charging

    # end == start
    # - both am
    # -- now before end, after start am, after start pm
    # - both pm
    # -- now before end am, before end pm, after start <====

    freezer.move_to("2022-10-01T02:00:00+02:00")

    entity_registry: EntityRegistry = async_entity_registry_get(hass)
    MockSOCEntity.create(hass, entity_registry, "66")
    MockTargetSOCEntity.create(hass, entity_registry, "80")
    MockPriceEntity.create(hass, entity_registry, 123)
    MockChargerEntity.create(hass, entity_registry, STATE_OFF)
    MockPriceEntity.set_state(hass, PRICE_20221001, None)
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_START_HOUR_3B, entry_id="test"
    )
    coordinator = EVSmartChargingCoordinator(hass, config_entry)
    assert coordinator is not None
    sensor: EVSmartChargingSensorCharging = EVSmartChargingSensorCharging(config_entry)
    assert sensor is not None
    await coordinator.add_sensor([sensor])
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await coordinator.switch_apply_limit_update(False)
    await coordinator.switch_continuous_update(True)
    await coordinator.switch_ev_connected_update(True)
    await coordinator.switch_keep_on_update(False)
    await hass.async_block_till_done()

    # Start_hour = 18:00, Ready_hour = 18:00
    # 5 hours => 03:00-08:00
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF
    assert coordinator.sensor.charging_is_planned is True
    assert coordinator.sensor.charging_start_time == datetime(
        2022, 10, 1, 3, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_stop_time == datetime(
        2022, 10, 1, 8, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_number_of_hours == 5

    # Start_hour = 18:00, Ready_hour = 18:00
    # 5 hours => 14:00-18:00
    freezer.move_to("2022-10-01T14:00:00+02:00")
    MockPriceEntity.set_state(hass, PRICE_20221001, PRICE_20221002)
    MockSOCEntity.set_state(hass, "67")
    await coordinator.switch_active_update(False)
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_ON
    assert coordinator.sensor.state == STATE_ON
    assert coordinator.sensor.charging_is_planned is True
    assert coordinator.sensor.charging_start_time == datetime(
        2022, 10, 1, 14, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_stop_time == datetime(
        2022, 10, 1, 18, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_number_of_hours == 4

    # Start_hour = 18:00, Ready_hour = 18:00
    # 5 hours => 03:00-08:00
    freezer.move_to("2022-10-01T20:00:00+02:00")
    MockSOCEntity.set_state(hass, "66")
    await coordinator.switch_active_update(False)
    await hass.async_block_till_done()
    await coordinator.switch_active_update(True)
    await hass.async_block_till_done()
    assert coordinator.auto_charging_state == STATE_OFF
    assert coordinator.sensor.state == STATE_OFF
    assert coordinator.sensor.charging_is_planned is True
    assert coordinator.sensor.charging_start_time == datetime(
        2022, 10, 2, 3, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_stop_time == datetime(
        2022, 10, 2, 8, 0, tzinfo=dt_util.get_time_zone("Europe/Stockholm")
    )
    assert coordinator.sensor.charging_number_of_hours == 5
