#!/usr/bin/env python3
"""Cerro speed control for desktops with a StatusNotifier tray."""
import os
from pathlib import Path
import tempfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

ITEM = "/StatusNotifierItem"
WATCHER = "org.kde.StatusNotifierWatcher"
PROPERTIES = {
    "Category": ("s", "Hardware"),
    "Id": ("s", "cerro-touchpad"),
    "Title": ("s", "Cerro 触摸板"),
    "Status": ("s", "Active"),
    "IconName": ("s", "input-touchpad"),
    "ItemIsMenu": ("b", False),
}
METHODS = ("Activate", "SecondaryActivate", "ContextMenu")


def write_speed(path, speed):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        try:
            stream.write(str(speed).encode("ascii"))
            stream.close()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)


def main():
    runtime = Path(os.environ["XDG_RUNTIME_DIR"]) / "cerro-touchpad-speed"
    config = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    saved = config / "cerro-touchpad" / "speed"
    try:
        speed = min(200, max(50, int(saved.read_text())))
    except (ValueError, OSError):
        speed = 100
    write_speed(runtime, speed)

    window = Gtk.Window(title="Cerro 触摸板")
    window.set_default_size(360, -1)
    window.connect("delete-event", lambda widget, _event: widget.hide_on_delete())
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
    window.add(box)
    label = Gtk.Label(label="鼠标移动速度", xalign=0)
    box.add(label)
    slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 200, 5)
    slider.set_value(speed)
    slider.connect("format-value", lambda _slider, value: f"{value:.0f}%")
    slider.get_accessible().set_name("鼠标移动速度")
    box.add(slider)
    reset = Gtk.Button(label="恢复默认速度")
    reset.connect("clicked", lambda _button: slider.set_value(100))
    box.add(reset)

    def change(widget):
        value = round(widget.get_value())
        write_speed(runtime, value)
        write_speed(saved, value)

    slider.connect("value-changed", change)
    xml = '<node><interface name="org.kde.StatusNotifierItem">'
    for name, (kind, _) in PROPERTIES.items():
        xml += f'<property name="{name}" type="{kind}" access="read"/>'
    for name in METHODS:
        xml += f'<method name="{name}"><arg type="i"/><arg type="i"/></method>'
    info = Gio.DBusNodeInfo.new_for_xml(xml + "</interface></node>")
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)

    def activate(_bus, _sender, _path, _iface, _method, _args, invocation):
        window.show_all()
        window.present()
        invocation.return_value(None)

    def prop(_bus, _sender, _path, _iface, name):
        return GLib.Variant(*PROPERTIES[name])

    bus.register_object(ITEM, info.interfaces[0], activate, prop, None)

    def register(connection, name, _owner):
        connection.call(name, "/StatusNotifierWatcher", WATCHER,
                        "RegisterStatusNotifierItem", GLib.Variant("(s)", (ITEM,)),
                        None, Gio.DBusCallFlags.NONE, 3000, None, None)

    Gio.bus_watch_name_on_connection(bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
                                      register, None)
    Gtk.main()


if __name__ == "__main__":
    main()
