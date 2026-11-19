#!/usr/bin/env python3
"""Clone a verified Cerro boot and add a one-shot Fedora root selector.

Only the embedded gzip cpio member changes. This tool does not flash a phone.
Pass a fresh readback of the *current* boot partition before deploying output.
"""

import argparse
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('cerro_splice', ROOT / 'tools/splice-verified-initramfs.py')
splice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(splice)
SELECTOR = (Path(__file__).parent / 'one-shot-selector.sh').read_bytes()


def init_range(cpio):
    pos = 0
    while pos + 110 <= len(cpio) and cpio[pos:pos + 6] == b'070701':
        header = cpio[pos:pos + 110]
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        name = cpio[pos + 110:pos + 110 + name_size - 1]
        start = (pos + 110 + name_size + 3) & ~3
        if name in (b'init', b'./init'):
            return start, size
        pos = (start + size + 3) & ~3
    raise ValueError('embedded init not found')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source_boot', type=Path)
    ap.add_argument('source_sha256', help='fresh readback digest, required')
    ap.add_argument('output_boot', type=Path)
    ap.add_argument('--persistent', action='store_true', help='boot Fedora by default')
    args = ap.parse_args()
    source = args.source_boot.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.source_sha256:
        raise ValueError('source boot SHA-256 mismatch')
    if len(source) != 100663296:
        raise ValueError('source is not a 96 MiB Cerro partition image')
    if args.source_boot.resolve() == args.output_boot.resolve():
        raise ValueError('output would overwrite source')
    start, end = splice.kernel_range(source)
    offset, old_gzip_size, cpio = splice.member(source[start:end])
    data_start, data_size = init_range(cpio)
    original = cpio[data_start:data_start + data_size]
    if not (b'setup_acm' in original and b'cerro-userland-debian' in original):
        raise ValueError('source init lacks established Cerro control/selector')
    if b'cerro-boot-fedora-once' in original:
        raise ValueError('source already contains Fedora selector')
    needle = b'SWITCH_ROOT=/sysroot'
    if original.count(needle) != 1:
        raise ValueError('source init has unexpected root selection layout')
    selector = SELECTOR
    if args.persistent:
        selector = (Path(__file__).parent / 'persistent-selector.sh').read_bytes()
    modified = original.rstrip(b'\n').replace(needle, selector + b'\n' + needle)
    if len(modified) > data_size:
        raise ValueError('selector exceeds embedded init entry')
    modified += b'\n' * (data_size - len(modified))
    cpio2 = bytearray(cpio)
    cpio2[data_start:data_start + data_size] = modified
    syntax = subprocess.run(['bash', '-n'], input=modified, capture_output=True)
    if syntax.returncode:
        raise ValueError('modified init shell syntax invalid: ' + syntax.stderr.decode())
    compressed = subprocess.run(
        ['libdeflate-gzip', '-12', '-c'], input=cpio2, capture_output=True, check=True
    ).stdout
    if len(compressed) > old_gzip_size:
        raise ValueError(f'compressed member grew {len(compressed)} > {old_gzip_size}')
    image_offset = start + offset
    result = (source[:image_offset] + compressed + bytes(old_gzip_size - len(compressed))
              + source[image_offset + old_gzip_size:])
    if len(result) != len(source):
        raise ValueError('boot image size changed')
    if result[:image_offset] != source[:image_offset] or \
       result[image_offset + old_gzip_size:] != source[image_offset + old_gzip_size:]:
        raise ValueError('data outside initramfs changed')
    check_offset, _, check_cpio = splice.member(result[start:end])
    if check_offset != offset or check_cpio != cpio2:
        raise ValueError('initramfs readback failed')
    args.output_boot.write_bytes(result)
    print(f'source_sha256={args.source_sha256}')
    print(f'output_sha256={hashlib.sha256(result).hexdigest()}')
    print(f'init_bytes={data_size} compressed={len(compressed)}/{old_gzip_size}')
    print(f'output={args.output_boot}')


if __name__ == '__main__':
    main()
