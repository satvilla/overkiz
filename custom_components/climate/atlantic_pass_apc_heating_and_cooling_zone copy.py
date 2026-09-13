"""Support for Atlantic Pass APC Heating and Cooling Zone."""

from datetime import timedelta
from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, LOGGER
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity
from ..executor import OverkizExecutor

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.STOP: HVACMode.OFF,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.COOLING: HVACMode.COOL,
    OverkizCommandParam.INTERNAL_SCHEDULING: HVACMode.AUTO,
    OverkizCommandParam.EXTERNAL_SCHEDULING: HVACMode.AUTO,
    OverkizCommandParam.ABSENCE: HVACMode.AUTO,
    OverkizCommandParam.MANU: HVACMode.AUTO,
    OverkizCommandParam.ECO: HVACMode.AUTO,
    OverkizCommandParam.COMFORT: HVACMode.AUTO,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
}

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.ABSENCE: PRESET_AWAY,

    OverkizCommandParam.DEROGATION: PRESET_AWAY,
    OverkizCommandParam.EXTERNAL_SETPOINT: PRESET_ECO,
    OverkizCommandParam.FROSTPROTECTION: PRESET_AWAY,
    OverkizCommandParam.MANU: PRESET_COMFORT,
    OverkizCommandParam.STOP: PRESET_NONE,
}

PRESET_MODES_TO_OVERKIZ: dict[str, str] = {
    PRESET_COMFORT: OverkizCommandParam.COMFORT,
    PRESET_ECO: OverkizCommandParam.ECO,
    PRESET_AWAY: OverkizCommandParam.ABSENCE,
}
OVERKIZ_TEMPERATURE_STATE_BY_PROFILE: dict[str, str] = {
    OverkizCommandParam.ECO: OverkizState.CORE_ECO_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizState.CORE_COMFORT_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.ABSENCE: OverkizState.CORE_ABSENCE_HEATING_TARGET_TEMPERATURE,
}

OVERKIZ_COOLING_TEMPERATURE_STATE_BY_PROFILE: dict[str, str] = {
    OverkizCommandParam.ECO: OverkizState.CORE_ECO_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizState.CORE_COMFORT_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.ABSENCE: OverkizState.CORE_ABSENCE_COOLING_TARGET_TEMPERATURE,
}

OVERKIZ_HEATING_TEMPERATURE_COMMAND_BY_PROFILE: dict[str, OverkizCommand] = {
    OverkizCommandParam.ECO: OverkizCommand.SET_ECO_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.ABSENCE: OverkizCommand.SET_ABSENCE_HEATING_TARGET_TEMPERATURE,
}

OVERKIZ_COOLING_TEMPERATURE_COMMAND_BY_PROFILE: dict[str, OverkizCommand] = {
    OverkizCommandParam.ECO: OverkizCommand.SET_ECO_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizCommand.SET_COMFORT_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.ABSENCE: OverkizCommand.SET_ABSENCE_COOLING_TARGET_TEMPERATURE,
}

OVERKIZ_HEATING_TEMPERATURE_REFRESH_BY_PROFILE: dict[str, OverkizCommand] = {
    OverkizCommandParam.ECO: OverkizCommand.REFRESH_ECO_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizCommand.REFRESH_COMFORT_HEATING_TARGET_TEMPERATURE,
}

OVERKIZ_COOLING_TEMPERATURE_REFRESH_BY_PROFILE: dict[str, OverkizCommand] = {
    OverkizCommandParam.ECO: OverkizCommand.REFRESH_ECO_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizCommand.REFRESH_COMFORT_COOLING_TARGET_TEMPERATURE,
}


class AtlanticPassAPCHeatingAndCoolingZone(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Heating and Cooling Zone Control."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return controls available for the current zone state."""
        if self.hvac_mode == HVACMode.OFF:
            return ClimateEntityFeature.TURN_ON

        return self._attr_supported_features

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # Temperature sensor use the same base_device_url and use the n+1 index
        self.temperature_device = (
            self.executor.linked_device(subsystem_id + 1)
            if (subsystem_id := self.device.identifier.subsystem_id) is not None
            else None
        )
        self.main_device = self.executor.linked_device(1)
        self.main_executor = (
            OverkizExecutor(self.main_device.device_url, coordinator)
            if self.main_device is not None
            else self.executor
        )
        self._zone_is_off = False
        self._last_operating_mode: HVACMode | None = None
        self._last_profile: str | None = None

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.temperature_device is not None and (
            temperature := self.temperature_device.states.get(
                OverkizState.CORE_TEMPERATURE
            )
        ):
            return cast(float, temperature.value)

        return None

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the HVAC mode exposed by this zone entity."""
        if self._zone_is_off:
            return HVACMode.OFF

        operating_mode = self.current_operating_mode
        if operating_mode == HVACMode.COOL:
            if (
                self.device.states.get_value(OverkizState.CORE_COOLING_ON_OFF)
                == OverkizCommandParam.OFF
            ):
                return HVACMode.OFF
        elif operating_mode == HVACMode.HEAT and (
            self.device.states.get_value(OverkizState.CORE_HEATING_ON_OFF)
            == OverkizCommandParam.OFF
        ):
            return HVACMode.OFF

        return HVACMode.AUTO

    @property
    def current_operating_mode(self) -> HVACMode:
        """Return the actual heating or cooling mode from the main device."""
        mode_device = self.main_device or self.device
        operating_mode = OVERKIZ_TO_HVAC_MODE.get(
            cast(
                str,
                mode_device.states.get_value(
                    OverkizState.IO_PASS_APC_OPERATING_MODE
                ),
            ),
            HVACMode.AUTO,
        )
        if operating_mode in (HVACMode.HEAT, HVACMode.COOL):
            self._last_operating_mode = operating_mode
        return operating_mode

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the actual heating or cooling action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.current_operating_mode == HVACMode.COOL:
            return HVACAction.COOLING
        if self.current_operating_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        return None

    @property
    def current_heating_profile(self) -> str:
        """Return current heating profile."""
        return cast(
            str,
            self.device.states.get_value(OverkizState.IO_PASS_APC_HEATING_PROFILE),
        )

    @property
    def current_cooling_profile(self) -> str:
        """Return current cooling profile."""
        return cast(
            str,
            self.device.states.get_value(OverkizState.IO_PASS_APC_COOLING_PROFILE),
        )

    

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY:
            await self._async_set_absence_mode()
            return

        if self.main_device is not None:
            await self.main_executor.async_execute_command(
                OverkizCommand.CANCEL_ABSENCE,
                refresh_afterwards=True,
            )

        self._zone_is_off = False
        mode = PRESET_MODES_TO_OVERKIZ[preset_mode]
        self._last_profile = mode
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_HEATING_MODE,
            mode,
            refresh_afterwards=True,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_COOLING_MODE,
            mode,
            refresh_afterwards=True,
        )


    async def _async_set_absence_mode(self) -> None:
        """Start absence mode on the main APC device."""
        if self.main_device is None:
            return

        now = dt_util.now()
        start_date = {
            "month": now.month,
            "hour": now.hour,
            "year": now.year,
            "weekday": now.weekday(),
            "day": now.day,
            "minute": now.minute,
            "second": now.second,
        }
        end = now + timedelta(days=365)
        end_date = {
            "month": end.month,
            "hour": end.hour,
            "year": end.year,
            "weekday": end.weekday(),
            "day": end.day,
            "minute": end.minute,
            "second": end.second,
        }
        await self.main_executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_START_DATE_TIME,
            start_date,
            refresh_afterwards=True,
        )
        await self.main_executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_END_DATE_TIME,
            end_date,
            refresh_afterwards=True,
        )
        await self.main_executor.async_execute_command(
            OverkizCommand.REFRESH_ZONES_PASS_APC_HEATING_PROFILE,
            refresh_afterwards=True,
        )
        await self.main_executor.async_execute_command(
            OverkizCommand.REFRESH_ZONES_PASS_APC_COOLING_PROFILE,
            refresh_afterwards=True,
        )
        await self.main_executor.async_execute_command(
            OverkizCommand.REFRESH_ZONES_TARGET_TEMPERATURE,
            refresh_afterwards=True,
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the zone HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.AUTO:
            if self.main_device is not None:
                await self.main_executor.async_execute_command(
                    OverkizCommand.CANCEL_ABSENCE,
                    refresh_afterwards=True,
                )
                await self.main_executor.async_execute_command(
                    OverkizCommand.REFRESH_ZONES_PASS_APC_HEATING_PROFILE,
                    refresh_afterwards=True,
                )
                await self.main_executor.async_execute_command(
                    OverkizCommand.REFRESH_ZONES_PASS_APC_COOLING_PROFILE,
                    refresh_afterwards=True,
                )

            self._zone_is_off = False
            operating_mode = self._last_operating_mode
            if operating_mode is None:
                mode_device = self.main_device or self.device
                operating_mode = OVERKIZ_TO_HVAC_MODE.get(
                    cast(
                        str,
                        mode_device.states.get_value(
                            OverkizState.IO_PASS_APC_OPERATING_MODE
                        ),
                    ),
                    HVACMode.AUTO,
                )
            await self.executor.async_execute_command(
                OverkizCommand.SET_PASS_APC_HEATING_MODE,
                OverkizCommandParam.INTERNAL_SCHEDULING,
                refresh_afterwards=True,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_PASS_APC_COOLING_MODE,
                OverkizCommandParam.INTERNAL_SCHEDULING,
                refresh_afterwards=True,
            )
            if operating_mode == HVACMode.COOL:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_ON_OFF,
                    OverkizCommandParam.OFF,
                    refresh_afterwards=True,
                )
                await self.executor.async_execute_command(
                    OverkizCommand.SET_COOLING_ON_OFF,
                    OverkizCommandParam.ON,
                    refresh_afterwards=True,
                )
            else:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_ON_OFF,
                    OverkizCommandParam.ON,
                    refresh_afterwards=True,
                )
                await self.executor.async_execute_command(
                    OverkizCommand.SET_COOLING_ON_OFF,
                    OverkizCommandParam.OFF,
                    refresh_afterwards=True,
                )


            # If the profile is still absence after canceling absence, restore the last profile
            current_operating_mode = self.current_operating_mode
            current_profile = (
                self.current_cooling_profile
                if current_operating_mode == HVACMode.COOL
                else self.current_heating_profile
            )
            if current_profile == OverkizCommandParam.ABSENCE:
                profile = self._last_profile
                if profile is None or profile == OverkizCommandParam.ABSENCE:
                    profile = OverkizCommandParam.COMFORT
                await self.executor.async_execute_command(
                    OverkizCommand.SET_PASS_APC_HEATING_MODE,
                    profile,
                    refresh_afterwards=True,
                )
                await self.executor.async_execute_command(
                    OverkizCommand.SET_PASS_APC_COOLING_MODE,
                    profile,
                    refresh_afterwards=True,
                )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the active mode for this zone."""
        self._zone_is_off = True
        mode_device = self.main_device or self.device
        operating_mode = OVERKIZ_TO_HVAC_MODE.get(
            cast(
                str,
                mode_device.states.get_value(OverkizState.IO_PASS_APC_OPERATING_MODE),
            ),
            HVACMode.AUTO,
        )
        if operating_mode in (HVACMode.HEAT, HVACMode.COOL):
            self._last_operating_mode = operating_mode
            current_profile = (
                self.current_cooling_profile
                if operating_mode == HVACMode.COOL
                else self.current_heating_profile
            )
            if current_profile != OverkizCommandParam.ABSENCE:
                self._last_profile = current_profile
        command = (
            OverkizCommand.SET_COOLING_ON_OFF
            if operating_mode == HVACMode.COOL
            else OverkizCommand.SET_HEATING_ON_OFF
        )
        await self.executor.async_execute_command(
            command,
            OverkizCommandParam.OFF,
            refresh_afterwards=True,
        )


    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self.hvac_mode == HVACMode.OFF:
            return PRESET_NONE

        current_operating_mode = self.current_operating_mode

        profile_state = (
            OverkizState.IO_PASS_APC_COOLING_PROFILE
            if current_operating_mode == HVACMode.COOL
            else OverkizState.IO_PASS_APC_HEATING_PROFILE
        )
            
        return OVERKIZ_TO_PRESET_MODES.get(
            cast(
                str,
                self.device.states.get_value(profile_state),
            )
        )


    @property
    @override
    def target_temperature(self) -> float | None:
        """Return hvac target temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return None

        if self.current_operating_mode == HVACMode.COOL:
            current_cooling_profile = self.current_cooling_profile
            if current_cooling_profile in OVERKIZ_COOLING_TEMPERATURE_STATE_BY_PROFILE:
                temperature_device = self.device
                if (
                    current_cooling_profile == OverkizCommandParam.ABSENCE
                    and self.main_device is not None
                ):
                    temperature_device = self.main_device
                return cast(
                    float,
                    temperature_device.states.get_value(
                        OVERKIZ_COOLING_TEMPERATURE_STATE_BY_PROFILE[
                            current_cooling_profile
                        ]
                    ),
                )
            return cast(
                float,
                self.device.states.get_value(
                    OverkizState.CORE_COOLING_TARGET_TEMPERATURE
                ),
            )

        current_heating_profile = self.current_heating_profile
        if current_heating_profile in OVERKIZ_TEMPERATURE_STATE_BY_PROFILE:
            temperature_device = self.device
            if (
                current_heating_profile == OverkizCommandParam.ABSENCE
                and self.main_device is not None
            ):
                temperature_device = self.main_device
            return cast(
                float,
                temperature_device.states.get_value(
                    OVERKIZ_TEMPERATURE_STATE_BY_PROFILE[current_heating_profile]
                ),
            )
        return cast(
            float, self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        is_cooling = self.current_operating_mode == HVACMode.COOL
        temperature_states = (
            OVERKIZ_COOLING_TEMPERATURE_STATE_BY_PROFILE
            if is_cooling
            else OVERKIZ_TEMPERATURE_STATE_BY_PROFILE
        )
        temperature_commands = (
            OVERKIZ_COOLING_TEMPERATURE_COMMAND_BY_PROFILE
            if is_cooling
            else OVERKIZ_HEATING_TEMPERATURE_COMMAND_BY_PROFILE
        )
        temperature_refresh_commands = (
            OVERKIZ_COOLING_TEMPERATURE_REFRESH_BY_PROFILE
            if is_cooling
            else OVERKIZ_HEATING_TEMPERATURE_REFRESH_BY_PROFILE
        )
        profile = (
            self.current_cooling_profile if is_cooling else self.current_heating_profile
        )
        target_temperature_command = temperature_commands.get(profile)

        if target_temperature_command is None:
            return

        if profile == OverkizCommandParam.ABSENCE:
            await self.main_executor.async_execute_command(
                target_temperature_command,
                temperature,
                refresh_afterwards=True,
            )
            return

        other_profile = (
            OverkizCommandParam.COMFORT
            if profile == OverkizCommandParam.ECO
            else OverkizCommandParam.ECO
        )
        other_temperature = cast(
            float | None,
            self.device.states.get_value(temperature_states[other_profile]),
        )
        commands: list[Command] = []

        if other_temperature is not None:
            if profile == OverkizCommandParam.ECO and temperature > other_temperature:
                commands.extend(
                    [
                        Command(
                            name=temperature_commands[other_profile],
                            parameters=[temperature + 0.5],
                        ),
                        Command(
                            name=temperature_refresh_commands[other_profile],
                            parameters=[],
                        ),
                    ]
                )
            elif (
                profile == OverkizCommandParam.COMFORT
                and temperature < other_temperature
            ):
                commands.extend(
                    [
                        Command(
                            name=temperature_commands[other_profile],
                            parameters=[temperature - 0.5],
                        ),
                        Command(
                            name=temperature_refresh_commands[other_profile],
                            parameters=[],
                        ),
                    ]
                )

        commands.extend(
            [
                Command(
                    name=target_temperature_command,
                    parameters=[temperature],
                ),
                Command(
                    name=temperature_refresh_commands[profile],
                    parameters=[],
                ),
            ]
        )
        await self.executor.async_execute_commands(commands)
