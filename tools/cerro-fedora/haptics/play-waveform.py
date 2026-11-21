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
DEVICE_NAME = "aw86927-haptics"


def load_waveform(path):
    if path is None:
        # Four cycles near the measured LRA resonance, with a quick decay.
        cycle = 102
        return [
            round(amplitude * math.sin(2 * math.pi * i / cycle))
            for amplitude in (30000, 15000, 6000, 2000)
            for i in range(cycle)
        ] + [0]

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


def upload_waveform(dev, samples, strength):
    data = (ctypes.c_int16 * len(samples))(*samples)
    periodic = ff.Periodic(
        waveform=ecodes.FF_CUSTOM,
        magnitude=round(strength * 32767),
        custom_len=len(data),
        custom_data=data,
    )
    return dev.upload_effect(ff.Effect(
        ecodes.FF_PERIODIC, -1, 0, ff.Trigger(0, 0),
        ff.Replay(math.ceil(len(data) * 1000 / SAMPLE_RATE), 0),
        ff.EffectType(ff_periodic_effect=periodic),
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waveform", nargs="?", help="mono 24 kHz 16-bit PCM WAV, up to 30 ms")
    parser.add_argument("--strength", type=float, default=0.65)
    parser.add_argument("--device", help="evdev path, autodetected by default")
    args = parser.parse_args()
    if not 1 / 32767 <= args.strength <= 1:
        parser.error("--strength must be greater than zero and at most 1")

    try:
        samples = load_waveform(args.waveform)
        with closing(InputDevice(args.device) if args.device else find_device()) as dev:
            if ecodes.FF_CUSTOM not in dev.capabilities().get(ecodes.EV_FF, []):
                raise OSError("this driver does not expose custom waveforms")
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
