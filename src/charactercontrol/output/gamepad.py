"""
Thin wrapper around vgamepad's VX360Gamepad.
Provides a clean interface that hides driver details and adds defensive defaults.
"""

import vgamepad as vg


# vgamepad uses int16 range for analog sticks: -32768 to +32767
STICK_MAX = 32767


class VirtualGamepad:
    """
    A virtual Xbox 360 controller. Holds state in memory and pushes to driver
    on update(). Stick values are accepted as floats in [-1.0, +1.0].
    """

    def __init__(self) -> None:
        self._gp = vg.VX360Gamepad()
        # Make sure the driver registers the controller immediately
        self._gp.update()

    # ---- Analog sticks ----

    def set_left_stick(self, x: float, y: float) -> None:
        """x,y in [-1.0, +1.0]. +x = right, +y = up (Xinput convention)."""
        self._gp.left_joystick_float(x_value_float=_clamp(x), y_value_float=_clamp(y))

    def set_right_stick(self, x: float, y: float) -> None:
        self._gp.right_joystick_float(x_value_float=_clamp(x), y_value_float=_clamp(y))

    # ---- Triggers ----

    def set_left_trigger(self, value: float) -> None:
        """value in [0.0, 1.0]."""
        self._gp.left_trigger_float(value_float=max(0.0, min(1.0, value)))

    def set_right_trigger(self, value: float) -> None:
        self._gp.right_trigger_float(value_float=max(0.0, min(1.0, value)))

    # ---- Buttons ----

    def press(self, button: vg.XUSB_BUTTON) -> None:
        self._gp.press_button(button=button)

    def release(self, button: vg.XUSB_BUTTON) -> None:
        self._gp.release_button(button=button)

    # ---- Driver sync ----

    def update(self) -> None:
        """Push current state to the driver. Call once per frame."""
        self._gp.update()

    def reset(self) -> None:
        """Zero all inputs. Useful on shutdown or recalibration."""
        self._gp.reset()
        self._gp.update()


def _clamp(v: float) -> float:
    return max(-1.0, min(1.0, v))