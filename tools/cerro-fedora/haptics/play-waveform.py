#!/usr/bin/env python3
"""Play a short 24 kHz haptic waveform on a Cerro AW86927."""
import argparse
import ctypes
from contextlib import closing
import math
import time
import wave

from evdev import InputDevice, ecodes, ff, list_devices

SAMPLE_RATE = 24000
MAX_SAMPLES = 720
SAMPLES_PER_CYCLE = 102
DEVICE_NAME = "aw86927-haptics"


def click_samples(amplitudes):
    # Use full cycles near the measured LRA resonance.
    return [
        round(amplitude * math.sin(2 * math.pi * i / SAMPLES_PER_CYCLE))
        for amplitude in amplitudes
        for i in range(SAMPLES_PER_CYCLE)
    ] + [0]


def load_waveform(path):
    if path is None:
        return click_samples((30000, 15000, 6000, 2000))

    with wave.open(path, "rb") as source:
        length = source.getnframes()
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError("expected a mono 24 kHz signed 16-bit PCM WAV")
        if not 2 <= length <= MAX_SAMPLES:
            raise ValueError(f"expected 2–{MAX_SAMPLES} samples (at most 30 ms)")
        data = source.readframes(length)
        if len(data) != length * 2:
            raise ValueError("truncated WAV")
        return [
            int.from_bytes(data[i:i + 2], "little", signed=True)
            for i in range(0, len(data), 2)
        ]


def find_device():
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except OSError:
            continue
        if dev.name == DEVICE_NAME:
            return dev
        dev.close()
    raise OSError(f"no accessible {DEVICE_NAME} input device")


def upload_waveform(dev, samples, strength, effect_id=-1):
    data = (ctypes.c_int16 * len(samples))(*samples)
    periodic = ff.Periodic(
        waveform=ecodes.FF_CUSTOM,
        magnitude=round(strength * 32767),
        custom_len=len(data),
        custom_data=data,
    )
    return dev.upload_effect(ff.Effect(
        ecodes.FF_PERIODIC, effect_id, 0, ff.Trigger(0, 0),
        ff.Replay(math.ceil(len(data) * 1000 / SAMPLE_RATE), 0),
        ff.EffectType(ff_periodic_effect=periodic),
    ))


def require_custom(dev):
    if ecodes.FF_CUSTOM not in dev.capabilities().get(ecodes.EV_FF, []):
        raise OSError("this driver does not expose custom waveforms")


def run_gui():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    burst = click_samples((30000, 30000))[:-1]
    presets = (
        ("A · 渐弱", load_waveform(None)),
        ("B · 双脉冲", burst + [0] * 264 + burst + [0]),
        ("C · 短按", click_samples((30000, -10000))),
    )

    class WaveformApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="org.cerro.Haptics")
            self.device = None
            self.effects = {}

        def do_activate(self):
            window = self.get_active_window()
            if window:
                window.present()
                return

            window = Gtk.ApplicationWindow(application=self, title="振动测试")
            window.set_default_size(340, 300)
            panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            panel.set_margin_top(18)
            panel.set_margin_bottom(18)
            panel.set_margin_start(18)
            panel.set_margin_end(18)
            window.set_child(panel)

            panel.append(Gtk.Label(label="强度（%）", xalign=0))
            self.strength = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 100, 5)
            self.strength.set_draw_value(True)
            self.strength.set_digits(0)
            self.strength.set_value(90)
            panel.append(self.strength)

            for label, samples in presets:
                button = Gtk.Button(label=label)
                button.set_size_request(-1, 48)
                button.connect("clicked", self.play, label, samples)
                panel.append(button)

            self.status = Gtk.Label(xalign=0, wrap=True)
            panel.append(self.status)
            window.present()

        def play(self, _button, label, samples):
            try:
                if self.device is None:
                    self.device = find_device()
                    require_custom(self.device)

                strength = int(self.strength.get_value())
                effect_id, previous_strength = self.effects.get(label, (-1, 0))
                if strength != previous_strength:
                    effect_id = upload_waveform(self.device, samples, strength / 100, effect_id)
                    self.effects[label] = (effect_id, strength)
                self.device.write(ecodes.EV_FF, effect_id, 1)
                self.status.set_text(f"已触发 {label}")
            except OSError as exc:
                self.close_device()
                self.status.set_text(f"无法触发振动：{exc}")

        def close_device(self):
            if self.device is not None:
                # evdev erases effects owned by this file descriptor on close.
                self.device.close()
                self.device = None
            self.effects.clear()

        def do_shutdown(self):
            self.close_device()
            Gtk.Application.do_shutdown(self)

    return WaveformApp().run([])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waveform", nargs="?", help="mono 24 kHz 16-bit PCM WAV, up to 30 ms")
    parser.add_argument("--strength", type=float, default=0.65)
    parser.add_argument("--device", help="evdev path, autodetected by default")
    parser.add_argument("--gui", action="store_true", help="open the GTK waveform tester")
    args = parser.parse_args()
    if args.gui:
        raise SystemExit(run_gui())
    if not 1 / 32767 <= args.strength <= 1:
        parser.error("--strength must be greater than zero and at most 1")

    try:
        samples = load_waveform(args.waveform)
        with closing(InputDevice(args.device) if args.device else find_device()) as dev:
            require_custom(dev)
            effect_id = upload_waveform(dev, samples, args.strength)
            try:
                dev.write(ecodes.EV_FF, effect_id, 1)
                # Keep the uploaded effect alive through I²C transfer and playback.
                time.sleep(0.2)
            finally:
                dev.erase_effect(effect_id)
    except (OSError, ValueError, wave.Error, EOFError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")


if __name__ == "__main__":
    main()
