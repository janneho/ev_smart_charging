"""Coordinator for EV Smart Charging"""

from datetime import datetime
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_change,
)
from homeassistant.const import STATE_ON, STATE_OFF

from .const import (
    CONF_CHARGER_ENTITY,
    CONF_MAX_PRICE,
    CONF_MIN_SOC,
    CONF_PCT_PER_HOUR,
    CONF_READY_HOUR,
    CONF_NORDPOOL_SENSOR,
    CONF_EV_SOC_SENSOR,
    CONF_EV_TARGET_SOC_SENSOR,
    DEFAULT_TARGET_SOC,
    SWITCH,
)
from .helpers.coordinator import (
    Raw,
    Scheduler,
    get_charging_value,
)
from .helpers.general import Validator, get_parameter
from .sensor import EVSmartChargingSensor

_LOGGER = logging.getLogger(__name__)


class EVSmartChargingCoordinator:
    """Coordinator class"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.config_entry = config_entry
        self.platforms = []
        self.listeners = []

        self.sensor = None
        self.switch_active = None
        self.switch_apply_limit = None
        self.nordpool_entity_id = None
        self.ev_soc_entity_id = None
        self.ev_target_soc_entity_id = None

        self.charger_switch = None
        if len(get_parameter(self.config_entry, CONF_CHARGER_ENTITY)) > 0:
            self.charger_switch = get_parameter(self.config_entry, CONF_CHARGER_ENTITY)

        self.scheduler = Scheduler()

        self.ev_soc = None
        self.ev_target_soc = None
        self.raw_today = None
        self.raw_tomorrow = None
        self.tomorrow_valid = False

        self.raw_two_days = None
        self._charging_schedule = None
        self.charging_pct_per_hour = get_parameter(self.config_entry, CONF_PCT_PER_HOUR)
        if self.charging_pct_per_hour is None or self.charging_pct_per_hour <= 0.0:
            self.charging_pct_per_hour = 6.0
        self.ready_hour = int(get_parameter(self.config_entry, CONF_READY_HOUR)[0:2])
        self.max_price = float(get_parameter(self.config_entry, CONF_MAX_PRICE))
        self.number_min_soc = int(get_parameter(self.config_entry, CONF_MIN_SOC))

        self.auto_charging_state = STATE_OFF

        # Update state once per hour.
        self.listeners.append(
            async_track_time_change(hass, self.update_state, minute=0, second=0)
        )

    @callback
    async def update_state(
        self, date_time: datetime = None
    ):  # pylint: disable=unused-argument
        """Called every hour"""
        _LOGGER.debug("EVSmartChargingCoordinator.update_state()")
        if self._charging_schedule is not None:
            charging_value = get_charging_value(self._charging_schedule)
            _LOGGER.debug("charging_value = %s", charging_value)
            turn_on_charging = (
                self.ev_soc is not None
                and self.number_min_soc is not None
                and charging_value is not None
                and charging_value != 0
                and (
                    self.sensor.current_price < self.max_price
                    or self.max_price == 0.0
                    or self.switch_apply_limit is False
                    or self.ev_soc < self.number_min_soc
                )
            )
            if (
                self.ev_soc is not None
                and self.ev_target_soc is not None
                and self.ev_soc >= self.ev_target_soc
            ):
                turn_on_charging = False

            _LOGGER.debug("turn_on_charging = %s", turn_on_charging)
            current_value = self.auto_charging_state == STATE_ON
            _LOGGER.debug("current_value = %s", current_value)
            if turn_on_charging and not current_value:
                # Turn on charging
                self.auto_charging_state = STATE_ON
                await self.turn_on_charging()
            if not turn_on_charging and current_value:
                # Turn off charging
                self.auto_charging_state = STATE_OFF
                await self.turn_off_charging()

    async def turn_on_charging(self):
        """Turn on charging"""
        _LOGGER.debug("Turn on charging")
        self.sensor.native_value = STATE_ON
        if self.charger_switch is not None:
            _LOGGER.debug("Before service call switch.turn_on: %s", self.charger_switch)
            await self.hass.services.async_call(
                domain=SWITCH,
                service=SERVICE_TURN_ON,
                target={"entity_id": self.charger_switch},
            )

    async def turn_off_charging(self):
        """Turn off charging"""
        _LOGGER.debug("Turn off charging")
        self.sensor.native_value = STATE_OFF
        if self.charger_switch is not None:
            _LOGGER.debug(
                "Before service call switch.turn_off: %s", self.charger_switch
            )
            await self.hass.services.async_call(
                domain=SWITCH,
                service=SERVICE_TURN_OFF,
                target={"entity_id": self.charger_switch},
            )

    async def add_sensor(self, sensor: EVSmartChargingSensor):
        """Set up sensor"""
        self.sensor = sensor

        self.nordpool_entity_id = get_parameter(self.config_entry, CONF_NORDPOOL_SENSOR)
        self.ev_soc_entity_id = get_parameter(self.config_entry, CONF_EV_SOC_SENSOR)
        self.ev_target_soc_entity_id = get_parameter(
            self.config_entry, CONF_EV_TARGET_SOC_SENSOR
        )

        self.listeners.append(
            async_track_state_change(
                self.hass,
                [
                    self.nordpool_entity_id,
                    self.ev_soc_entity_id,
                ],
                self.update_sensors,
            )
        )
        if len(self.ev_target_soc_entity_id) > 0:
            self.listeners.append(
                async_track_state_change(
                    self.hass,
                    [
                        self.ev_target_soc_entity_id,
                    ],
                    self.update_sensors,
                )
            )
        else:
            # Set default Target SOC when there is no sensor
            self.sensor.ev_target_soc = DEFAULT_TARGET_SOC
            self.ev_target_soc = DEFAULT_TARGET_SOC

        self._charging_schedule = Scheduler.get_empty_schedule()
        self.sensor.charging_schedule = self._charging_schedule
        await self.update_sensors()

    async def switch_active_update(self, state: bool):
        """Handle the Active switch"""
        self.switch_active = state
        _LOGGER.debug("switch_active_update = %s", state)
        await self.update_sensors()

    async def switch_apply_limit_update(self, state: bool):
        """Handle the Active switch"""
        self.switch_apply_limit = state
        _LOGGER.debug("switch_apply_limit_update = %s", state)
        await self.update_sensors()

    @callback
    async def update_sensors(
        self, entity_id: str = None, old_state: State = None, new_state: State = None
    ):  # pylint: disable=unused-argument
        """Nordpool or EV sensors have been updated."""

        _LOGGER.debug("EVSmartChargingCoordinator.update_sensors()")
        _LOGGER.debug("entity_id = %s", entity_id)
        # _LOGGER.debug("old_state = %s", old_state)
        _LOGGER.debug("new_state = %s", new_state)

        nordpool_state = self.hass.states.get(self.nordpool_entity_id)
        if Validator.is_nordpool_state(nordpool_state):
            self.sensor.current_price = nordpool_state.attributes["current_price"]
            self.raw_today = Raw(nordpool_state.attributes["raw_today"])
            self.raw_tomorrow = Raw(nordpool_state.attributes["raw_tomorrow"])
            self.tomorrow_valid = self.raw_tomorrow.is_valid()
            self.raw_two_days = self.raw_today.copy()
            self.raw_two_days.extend(self.raw_tomorrow)
            self.sensor.raw_two_days = self.raw_two_days.get_raw()
        else:
            _LOGGER.error("Nordpool sensor not valid.")

        ev_soc_state = self.hass.states.get(self.ev_soc_entity_id)
        if Validator.is_soc_state(ev_soc_state):
            self.sensor.ev_soc = ev_soc_state.state
            self.ev_soc = float(ev_soc_state.state)
        else:
            _LOGGER.error("SOC sensor not valid: %s", ev_soc_state)

        if len(self.ev_target_soc_entity_id) > 0:
            ev_target_soc_state = self.hass.states.get(self.ev_target_soc_entity_id)
            if Validator.is_soc_state(ev_target_soc_state):
                self.sensor.ev_target_soc = ev_target_soc_state.state
                self.ev_target_soc = float(ev_target_soc_state.state)
            else:
                _LOGGER.error("Target SOC sensor not valid: %s", ev_target_soc_state)

        # Calculate charging schedule if tomorrow's prices are available,
        # SOC and target SOC are available and if the auto charging state is off
        scheduling_params = {
            "ev_soc": self.ev_soc,
            "ev_target_soc": self.ev_target_soc,
            "min_soc": self.number_min_soc,
            "charging_pct_per_hour": self.charging_pct_per_hour,
            "ready_hour": self.ready_hour,
            "switch_active": self.switch_active,
            "switch_apply_limit": self.switch_apply_limit,
            "max_price": self.max_price,
        }

        if self.tomorrow_valid and self.auto_charging_state == STATE_OFF:
            self.scheduler.create_base_schedule(scheduling_params, self.raw_two_days)

        if self.scheduler.base_schedule_exists() is True:
            scheduling_params.update(
                {"value_in_graph": self.raw_two_days.max_value() * 0.75}
            )
            new_charging = self.scheduler.get_schedule(scheduling_params)
            if new_charging is not None:
                self._charging_schedule = new_charging
                self.sensor.charging_schedule = self._charging_schedule

        _LOGGER.debug("self._max_price = %s", self.max_price)
        _LOGGER.debug("Current price = %s", self.sensor.current_price)
        await self.update_state()  # Update the charging status

    def validate_input_sensors(self) -> str:
        """Check that all input sensors returns values."""

        nordpool = get_parameter(self.config_entry, CONF_NORDPOOL_SENSOR)
        nordpool_state = self.hass.states.get(nordpool)
        if nordpool_state is None:
            return "Input sensors not ready."

        ev_soc = get_parameter(self.config_entry, CONF_EV_SOC_SENSOR)
        ev_soc_state = self.hass.states.get(ev_soc).state
        if ev_soc_state is None:
            return "Input sensors not ready."

        ev_target_soc = get_parameter(self.config_entry, CONF_EV_TARGET_SOC_SENSOR)
        if len(ev_target_soc) > 0:  # Check if the sensor exists
            ev_target_soc_state = self.hass.states.get(ev_target_soc).state
            if ev_target_soc_state is None:
                return "Input sensors not ready."

        return None
