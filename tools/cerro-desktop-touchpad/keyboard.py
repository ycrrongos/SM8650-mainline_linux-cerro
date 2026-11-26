"""The keyboard layout and physical keyboard detection for the Cerro relay."""

from pathlib import Path

from evdev import ecodes as E

KEYBOARD_TOP = 0.12
SWITCH_LEFT = 0.88
SWITCH_BOTTOM = 0.11


def on_switch(x, y):
    return x >= SWITCH_LEFT and y < SWITCH_BOTTOM
ROWS = (
    (("Esc", "ESC", 1.1), *[(s, s, 1) for s in "1234567890"],
     ("−", "MINUS", 1), ("=", "EQUAL", 1), ("⌫", "BACKSPACE", 1.4)),
    (("Tab", "TAB", 1.4), *[(s, s, 1) for s in "QWERTYUIOP"],
     ("[", "LEFTBRACE", 1), ("]", "RIGHTBRACE", 1), ("\\", "BACKSLASH", 1)),
    (("Shift", "LEFTSHIFT", 1.5), *[(s, s, 1) for s in "ASDFGHJKL"],
     (";", "SEMICOLON", 1), ("'", "APOSTROPHE", 1), ("Enter", "ENTER", 1.8)),
    (("Ctrl", "LEFTCTRL", 1.5), *[(s, s, 1) for s in "ZXCVBNM"],
     (",", "COMMA", 1), (".", "DOT", 1), ("/", "SLASH", 1), ("↑", "UP", 1)),
    (("Super", "LEFTMETA", 1.5), ("Alt", "LEFTALT", 1.5), ("空格", "SPACE", 6),
     ("←", "LEFT", 1), ("↓", "DOWN", 1), ("→", "RIGHT", 1)),
)
MODIFIERS = {E.KEY_LEFTSHIFT, E.KEY_LEFTCTRL, E.KEY_LEFTMETA, E.KEY_LEFTALT}


def layout():
    keys = []
    for row, definitions in enumerate(ROWS):
        x = 0
        total = sum(weight for _, _, weight in definitions)
        for label, name, weight in definitions:
            width = weight / total
            keys.append(dict(label=label, code=E.ecodes["KEY_" + name],
                             x=x, y=row / len(ROWS), w=width,
                             h=1 / len(ROWS)))
            x += width
    return keys


KEYS = layout()


def key_at(x, y):
    y = (y - KEYBOARD_TOP) / (1 - KEYBOARD_TOP)
    return next((key["code"] for key in KEYS
                 if key["x"] <= x < key["x"] + key["w"]
                 and key["y"] <= y < key["y"] + key["h"]), None)


def physical_keyboard(sys_input=Path("/sys/class/input"), database=Path("/run/udev/data")):
    for event in sys_input.glob("event*"):
        try:
            bus = (event / "device/id/bustype").read_text().strip()
            if bus not in ("0003", "0005"):  # USB, including receivers, or Bluetooth.
                continue
            major_minor = (event / "dev").read_text().strip()
            properties = (database / f"c{major_minor}").read_text().splitlines()
        except FileNotFoundError:
            continue  # The event node or its udev record is still changing.
        if "E:ID_INPUT_KEYBOARD=1" in properties:
            seat = next((item.partition("=")[2] for item in properties
                         if item.startswith("E:ID_SEAT=")), "seat0")
            if seat == "seat0":
                return True
    return False


class Keyboard:
    def __init__(self, output):
        self.output = output
        self.modifiers = set()
        self.last_key = None
        self.changed = False

    def press(self, code):
        self.last_key = code
        self.changed = True
        if code in MODIFIERS:
            self.modifiers.symmetric_difference_update([code])
            return

        modifiers = sorted(self.modifiers)
        for key in modifiers:
            self.output.write(E.EV_KEY, key, 1)
        self.output.write(E.EV_KEY, code, 1)
        self.output.syn()
        self.output.write(E.EV_KEY, code, 0)
        for key in reversed(modifiers):
            self.output.write(E.EV_KEY, key, 0)
        self.output.syn()
        self.modifiers.clear()
