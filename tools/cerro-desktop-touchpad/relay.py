#!/usr/bin/env python3
"""Forward Goodix protocol B contacts to a native libinput touchpad."""
import argparse
import errno
import select
from dataclasses import dataclass
from pathlib import Path

from evdev import AbsInfo, InputDevice, UInput, ecodes as E

NAME = "Cerro Desktop Touchpad"
TOOLS = (E.BTN_TOOL_FINGER, E.BTN_TOOL_DOUBLETAP,
         E.BTN_TOOL_TRIPLETAP, E.BTN_TOOL_QUADTAP, E.BTN_TOOL_QUINTTAP)
X, Y = E.ABS_MT_POSITION_X, E.ABS_MT_POSITION_Y


@dataclass
class Contact:
    tracking_id: int
    x: int | None = None
    y: int | None = None


class Touchpad:
    def __init__(self, source, rotation):
        self.rotation = rotation
        self.bounds = {code: source.absinfo(code) for code in (X, Y)}
        slots = source.absinfo(E.ABS_MT_SLOT)
        if slots.min != 0 or slots.max < 2:
            raise ValueError("Expected a protocol B touchscreen with at least three slots")
        self.slots = slots
        self.contacts = {}
        self.active = {}
        self.slot = 0
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

    def position(self, contact):
        def normalize(value, code):
            info = self.bounds[code]
            return min(1, max(0, (value - info.min) / (info.max - info.min)))

        x, y = normalize(contact.x, X), normalize(contact.y, Y)
        x, y = {0: (x, y), 90: (y, 1-x), 180: (1-x, 1-y),
                270: (1-y, x)}[self.rotation]
        return round(x * self.width), round(y * self.height)

    def flush(self, output):
        ready = {slot: contact for slot, contact in self.contacts.items()
                 if contact.x is not None and contact.y is not None}
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
        self.active = {slot: contact.tracking_id for slot, contact in ready.items()}

    def relay(self, source, output, connector):
        while connector.read_text().strip() == "connected":
            if not select.select([source.fd], [], [], 0.25)[0]:
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
                    self.contacts.pop(self.slot, None)
                else:
                    self.contacts[self.slot] = Contact(event.value)
            elif self.slot in self.contacts:
                contact = self.contacts[self.slot]
                if event.code == X:
                    contact.x = event.value
                elif event.code == Y:
                    contact.y = event.value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", type=Path)
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=90)
    parser.add_argument("--connector", type=Path,
                        default=Path("/sys/class/drm/card0-DP-1/status"))
    args = parser.parse_args()
    if args.connector.read_text().strip() != "connected":
        parser.error("Connect an external display before enabling the relay")
    source = InputDevice(str(args.device))
    if source.name != "Goodix Berlin Capacitive TouchScreen":
        source.close()
        parser.error("Refusing to grab a device other than the Cerro touchscreen")
    try:
        touchpad = Touchpad(source, args.rotate)
        with UInput(touchpad.capabilities, name=NAME, bustype=E.BUS_VIRTUAL,
                    input_props=[E.INPUT_PROP_POINTER, E.INPUT_PROP_BUTTONPAD]) as output:
            with source.grab_context():
                touchpad.relay(source, output, args.connector)
    finally:
        source.close()


if __name__ == "__main__":
    main()
