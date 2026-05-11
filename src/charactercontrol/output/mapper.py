"""
GamepadMapper: applies a Profile to BodyState + GestureEvents and updates
a VirtualGamepad accordingly.
"""

from typing import Iterable
import vgamepad as vg

from charactercontrol.pose.types import BodyState
from charactercontrol.gestures.events import GestureEvent, GestureKind, EventPhase
from charactercontrol.output.gamepad import VirtualGamepad
from charactercontrol.output.profiles import Profile, AnalogMapping


# Map button names (used in profile JSON) to vgamepad enum values.
BUTTON_NAMES = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
}


class GamepadMapper:
    """
    Applies a Profile to runtime BodyState and gesture events.

    Per frame:
        1. Compute analog stick/trigger values from continuous BodyState attrs.
        2. Process discrete gesture events into button press/release calls.
        3. Push the updated state to the gamepad driver.
    """

    def __init__(self, profile: Profile, gamepad: VirtualGamepad) -> None:
        self._profile = profile
        self._gamepad = gamepad
        # Track current analog target values so we can write them as a unit.
        self._analog_state: dict[str, float] = {
            "left_stick_x": 0.0, "left_stick_y": 0.0,
            "right_stick_x": 0.0, "right_stick_y": 0.0,
            "left_trigger": 0.0, "right_trigger": 0.0,
        }

    def update(self, state: BodyState, events: Iterable[GestureEvent]) -> None:
        """Apply state and events to the gamepad. Call once per frame."""
        # ---- Analog ----
        for mapping in self._profile.analog:
            value = getattr(state, mapping.source, None)
            if value is None:
                continue
            output = _scale_with_deadzone(
                value, mapping.deadzone, mapping.full_scale
            )
            if mapping.invert:
                output = -output
            self._analog_state[mapping.target] = output
        
        print(
            f"\rstick=({self._analog_state['left_stick_x']:+.3f}, "
            f"{self._analog_state['left_stick_y']:+.3f})",
            end="", flush=True,
)
        self._gamepad.set_left_stick(
            self._analog_state["left_stick_x"],
            self._analog_state["left_stick_y"],
        )
        self._gamepad.set_right_stick(
            self._analog_state["right_stick_x"],
            self._analog_state["right_stick_y"],
        )
        self._gamepad.set_left_trigger(self._analog_state["left_trigger"])
        self._gamepad.set_right_trigger(self._analog_state["right_trigger"])

        # ---- Buttons (from gesture events) ----
        for event in events:
            for button_map in self._profile.buttons:
                if button_map.gesture != event.kind.name:
                    continue
                button = BUTTON_NAMES.get(button_map.button)
                if button is None:
                    continue
                if event.phase == EventPhase.START:
                    self._gamepad.press(button)
                else:
                    self._gamepad.release(button)

        # Push everything to the driver
        self._gamepad.update()


def _scale_with_deadzone(value: float, deadzone: float, full_scale: float) -> float:
    """
    Map a continuous input to [-1.0, +1.0] with a deadzone and saturation.
    
    - |value| <= deadzone → 0.0
    - |value| >= full_scale → ±1.0
    - In between, linear scaling.
    """
    abs_v = abs(value)
    if abs_v <= deadzone:
        return 0.0
    if abs_v >= full_scale:
        return 1.0 if value > 0 else -1.0
    # Linear scale in the active range
    sign = 1.0 if value > 0 else -1.0
    scaled = (abs_v - deadzone) / (full_scale - deadzone)
    return sign * scaled