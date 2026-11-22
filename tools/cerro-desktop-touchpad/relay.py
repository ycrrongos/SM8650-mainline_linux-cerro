#!/usr/bin/env python3
"""Forward Goodix protocol B contacts to a native libinput touchpad."""
import argparse
import errno
import json
import select
import socket
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from evdev import AbsInfo, InputDevice, UInput, ecodes as E

from keyboard import KEYS, SPLIT, Keyboard, key_at, physical_keyboard

NAME = "Cerro Desktop Touchpad"
TOOLS = (E.BTN_TOOL_FINGER, E.BTN_TOOL_DOUBLETAP,
         E.BTN_TOOL_TRIPLETAP, E.BTN_TOOL_QUADTAP, E.BTN_TOOL_QUINTTAP)
X, Y = E.ABS_MT_POSITION_X, E.ABS_MT_POSITION_Y


@dataclass
class Contact:
    tracking_id: int
    x: int | None = None
    y: int | None = None
    route: str | None = None
    key: int | None = None


class Ripple:
    """Send dashboard state without waiting on its socket."""

    def __init__(self, path):
        self.path = str(path)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_NONBLOCK)
        self.last_time = 0
        self.last_point = None

    def send(self, message):
        try:
            self.socket.sendto(message, self.path)
        except OSError:
            pass

    def layout(self, split, keyboard, include_keys):
        data = {"split": SPLIT if split else 0, "key": keyboard.last_key,
                "modifiers": sorted(keyboard.modifiers), "pressed": keyboard.changed}
        if include_keys:
            data["keys"] = KEYS
        self.send(json.dumps(data, separators=(",", ":")).encode())

    def update(self, point):
        now = time.monotonic()
        if point is None:
            self.last_point = None
            return
        if self.last_point is not None:
            dx = point[0] - self.last_point[0]
            dy = point[1] - self.last_point[1]
            if now - self.last_time < 0.055 or dx * dx + dy * dy < 0.00018:
                return
        self.last_point = point
        self.last_time = now
        self.send(f"{point[0]:.4f} {point[1]:.4f}".encode())


class Touchpad:
    def __init__(self, source, rotation, ripple=None):
        self.rotation = rotation
        self.ripple = ripple
        self.bounds = {code: source.absinfo(code) for code in (X, Y)}
        slots = source.absinfo(E.ABS_MT_SLOT)
        if slots.min != 0 or slots.max < 2:
            raise ValueError("Expected a protocol B touchscreen with at least three slots")
        self.slots = slots
        self.contacts = {}
        self.active = {}
        self.slot = 0
        self.split = False
        self.keyboard = None
        width, height = (157, 71) if rotation in (90, 270) else (71, 157)
        self.width, self.height = width * 20, height * 20
        horizontal = AbsInfo(0, 0, self.width, 0, 0, 20)
        vertical = AbsInfo(0, 0, self.height, 0, 0, 20)
        self.capabilities = {
            E.EV_KEY: [E.BTN_TOUCH, E.BTN_LEFT, *TOOLS],
            E.EV_ABS: [
                (E.ABS_X, horizontal), (E.ABS_Y, vertical),
                (X, horizontal), (Y, vertical), (E.ABS_MT_SLOT, slots),
                (E.ABS_MT_TRACKING_ID, AbsInfo(0, 0, 65535, 0, 0, 0)),
            ],
        }

    def normalized(self, contact):
        def normalize(value, code):
            info = self.bounds[code]
            return min(1, max(0, (value - info.min) / (info.max - info.min)))

        x, y = normalize(contact.x, X), normalize(contact.y, Y)
        x, y = {0: (x, y), 90: (y, 1-x), 180: (1-x, 1-y),
                270: (1-y, x)}[self.rotation]
        return x, y

    def position(self, contact):
        x, y = self.normalized(contact)
        if self.split:
            x = max(0, (x - SPLIT) / (1 - SPLIT))
        return round(x * self.width), round(y * self.height)

    def release(self, slot, allow_key):
        contact = self.contacts.pop(slot, None)
        if allow_key and contact is not None and contact.route == "keyboard":
            if contact.key is not None:
                self.keyboard.press(contact.key)

    def route(self, contact):
        x, y = self.normalized(contact)
        if contact.route is None:
            if self.split and x < SPLIT:
                contact.route, contact.key = "keyboard", key_at(x, y)
            else:
                contact.route = "touchpad"
        elif contact.route == "keyboard" and key_at(x, y) != contact.key:
            # A touch that slides away from its key never types on release.
            contact.key = None

    def flush(self, output):
        ready = {}
        for slot, contact in self.contacts.items():
            if contact.x is None or contact.y is None:
                continue
            self.route(contact)
            if contact.route == "touchpad":
                ready[slot] = contact
        key = min(len(ready), len(TOOLS))
        output.write(E.EV_KEY, E.BTN_TOUCH, bool(key))
        for count, button in enumerate(TOOLS, 1):
            output.write(E.EV_KEY, button, count == key)
        for slot in sorted(self.active.keys() | ready.keys()):
            output.write(E.EV_ABS, E.ABS_MT_SLOT, slot)
            contact = ready.get(slot)
            previous = self.active.get(slot)
            if previous is not None and (not contact or previous != contact.tracking_id):
                output.write(E.EV_ABS, E.ABS_MT_TRACKING_ID, -1)
            if contact:
                if previous != contact.tracking_id:
                    output.write(E.EV_ABS, E.ABS_MT_TRACKING_ID, contact.tracking_id)
                x, y = self.position(contact)
                output.write(E.EV_ABS, X, x)
                output.write(E.EV_ABS, Y, y)
        if ready:
            primary = next(iter(ready.values()))
            x, y = self.position(primary)
            output.write(E.EV_ABS, E.ABS_X, x)
            output.write(E.EV_ABS, E.ABS_Y, y)
        output.syn()
        if self.ripple:
            self.ripple.update(self.normalized(primary) if ready else None)
        self.active = {slot: contact.tracking_id for slot, contact in ready.items()}

    def relay(self, source, output, connector, heartbeat):
        next_detection = 0
        needs_keyboard = False
        while connector.read_text().strip() == "connected":
            if heartbeat is not None and not fresh(heartbeat):
                return
            now = time.monotonic()
            refresh = self.keyboard is not None and now >= next_detection
            if refresh:
                needs_keyboard = not physical_keyboard()
                next_detection = now + 0.75
            mode_changed = self.keyboard is not None and not self.contacts and self.split != needs_keyboard
            if mode_changed:
                self.split = needs_keyboard
                self.keyboard.modifiers.clear()
                self.keyboard.last_key = None
            if self.ripple and self.keyboard and (refresh or mode_changed or self.keyboard.changed):
                self.ripple.layout(self.split, self.keyboard, refresh or mode_changed)
                self.keyboard.changed = False
            if not select.select([source.fd], [], [], 0.12)[0]:
                continue
            try:
                events = list(source.read())
            except BlockingIOError:
                continue
            for event in events:
                self.handle(event, output)

    def handle(self, event, output):
        if event.type == E.EV_SYN:
            if event.code == E.SYN_DROPPED:
                raise OSError(errno.EOVERFLOW, "Touchscreen event stream overrun")
            if event.code == E.SYN_REPORT:
                self.flush(output)
        elif event.type == E.EV_ABS:
            if event.code == E.ABS_MT_SLOT:
                self.slot = event.value
            elif event.code == E.ABS_MT_TRACKING_ID:
                if event.value < 0:
                    self.release(self.slot, allow_key=True)
                else:
                    self.release(self.slot, allow_key=False)
                    self.contacts[self.slot] = Contact(event.value)
            elif self.slot in self.contacts:
                contact = self.contacts[self.slot]
                if event.code == X:
                    contact.x = event.value
                elif event.code == Y:
                    contact.y = event.value


def fresh(path):
    try:
        return 0 <= time.time() - path.stat().st_mtime < 3
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", type=Path)
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=90)
    parser.add_argument("--connector", type=Path,
                        default=Path("/sys/class/drm/card0-DP-1/status"))
    parser.add_argument("--heartbeat", type=Path)
    parser.add_argument("--ripple-socket", type=Path)
    parser.add_argument("--auto-keyboard", action="store_true")
    args = parser.parse_args()
    if args.heartbeat is not None and not fresh(args.heartbeat):
        parser.error("Dashboard heartbeat is missing or stale")
    if args.connector.read_text().strip() != "connected":
        parser.error("Connect an external display before enabling the relay")
    source = InputDevice(str(args.device))
    if source.name != "Goodix Berlin Capacitive TouchScreen":
        source.close()
        parser.error("Refusing to grab a device other than the Cerro touchscreen")
    try:
        ripple = Ripple(args.ripple_socket) if args.ripple_socket else None
        touchpad = Touchpad(source, args.rotate, ripple)
        with UInput(touchpad.capabilities, name=NAME, bustype=E.BUS_VIRTUAL,
                    input_props=[E.INPUT_PROP_POINTER, E.INPUT_PROP_BUTTONPAD]) as output:
            with ExitStack() as devices:
                if args.auto_keyboard and ripple:
                    try:
                        keyboard = devices.enter_context(UInput(
                            {E.EV_KEY: [key["code"] for key in KEYS]},
                            name="Cerro Virtual Keyboard", bustype=E.BUS_VIRTUAL,
                        ))
                    except OSError as exc:
                        print(f"Cannot create virtual keyboard: {exc}", file=sys.stderr)
                    else:
                        touchpad.keyboard = Keyboard(keyboard)
                devices.enter_context(source.grab_context())
                touchpad.relay(source, output, args.connector, args.heartbeat)
    finally:
        source.close()


if __name__ == "__main__":
    main()
