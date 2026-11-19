#!/usr/bin/env python3
"""Package a Cerro Fedora kernel with its matching early and runtime modules."""

import argparse
import hashlib
import runpy
import shutil
import subprocess
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("reference_boot", type=Path, help="Verified running Fedora boot readback")
parser.add_argument("reference_sha", help="SHA-256 of the readback")
parser.add_argument("built_boot", type=Path, help="Built replacement boot image")
parser.add_argument("kernel", type=Path, help="Matching built Cerro kernel tree")
parser.add_argument("external_modules", type=Path, help="Matching camera module build directories")
parser.add_argument("reference_modules", type=Path, help="Tar archive of the live module files")
parser.add_argument("work", type=Path, help="New output directory")
args = parser.parse_args()
work = args.work
kernel = args.kernel
old_version = "7.2.0-rc5-dirty"
new_version = old_version + "-fedora-zram"
runtime = work / "runtime"
bootstage = work / "initrd"
source_boot = args.reference_boot
built_boot = args.built_boot
out_boot = work / "linux-fedora-zram-UNTESTED.img"
work.mkdir()
modtools = runpy.run_path(str(Path(__file__).resolve().parents[1] / "splice-verified-initramfs.py"))
required = {}
for root in (kernel, args.external_modules):
    for path in root.rglob("*.ko"):
        if path.name in required:
            raise ValueError(f"Ambiguous module {path.name}")
        required[path.name] = path

cache = work / "zram-stripped"
cache.mkdir(exist_ok=True)


def prepare(filename):
    target = cache / filename
    if not target.exists():
        source = required[filename]
        version = subprocess.check_output(["modinfo", "-F", "vermagic", source], text=True).split()[0]
        assert version == new_version, (source, version)
        subprocess.run(["llvm-strip", "--strip-debug", "-o", target, source], check=True)
    return target


def depmod(root):
    modules = root / "lib/modules" / new_version
    for filename in ("modules.builtin", "modules.builtin.modinfo"):
        shutil.copyfile(kernel / filename, modules / filename)
    (modules / "modules.order").write_text("".join(f"{file.relative_to(modules)}\n" for file in sorted(modules.rglob("*.ko"))))
    result = subprocess.run(["depmod", "-b", root, "-F", kernel / "System.map", "-ae", new_version],
                            check=True, capture_output=True, text=True)
    (root / "depmod.stderr").write_text(result.stderr)
    return {p.name: p.read_bytes() for p in modules.glob("modules.*")}


builtins = {Path(name).name for name in (kernel / "modules.builtin").read_text().splitlines()}
assert "pci-pwrctrl-pwrseq.ko" in builtins

target = runtime / "lib/modules" / new_version
target.mkdir(parents=True)
with tarfile.open(args.reference_modules) as archive:
    paths = [Path(entry.name) for entry in archive.getmembers() if entry.isfile() and entry.name.endswith(".ko") and Path(entry.name).name not in builtins]
for name in paths + [Path("kernel/mm/zsmalloc.ko"), Path("kernel/drivers/block/zram/zram.ko"), Path("kernel/drivers/soc/ti/pruss.ko")]:
    assert not name.is_absolute() and ".." not in name.parts
    new = target / name
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(prepare(name.name), new)
depmod(runtime)

source = source_boot.read_bytes()
assert hashlib.sha256(source).hexdigest() == args.reference_sha
first, last = modtools["kernel_range"](source)
_, _, cpio = modtools["member"](source[first:last])
early_modules = bootstage / "lib/modules" / new_version
early_modules.mkdir(parents=True)
contents = modtools["entries"](cpio)
for name in contents:
    prefix = f"usr/lib/modules/{old_version}/"
    if name.startswith(prefix) and name.endswith(".ko"):
        path = early_modules / name.removeprefix(prefix)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(prepare(path.name), path)
extra_early = ("kernel/drivers/soc/ti/pruss.ko", "kernel/drivers/media/mc/mc.ko")
for filename in extra_early:
    path = early_modules / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(prepare(path.name), path)
metadata = depmod(bootstage)
for stage in (runtime, bootstage):
    warnings = (stage / "depmod.stderr").read_text().strip()
    if warnings:
        raise ValueError(warnings)


def pad(data):
    return data + b"\0" * (-len(data) % 4)


def encoded_entry(filename, data, mode, inode):
    filename = str(filename).encode() + b"\0"
    values = (inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(filename), 0)
    header = b"070701" + "".join(f"{value:08x}" for value in values).encode()
    return [pad(header + filename), pad(data)]


def append_extra_entries(chunks):
    seen = set(contents)
    inode = 0x7FFF0000
    for extra in extra_early:
        path = Path("usr/lib/modules") / old_version / extra
        for parent in reversed(path.parents):
            if parent == Path(".") or str(parent) in seen:
                continue
            filename = str(parent).replace(old_version, new_version)
            chunks.extend(encoded_entry(filename, b"", 0o40755, inode))
            inode += 1
            seen.add(str(parent))
        filename = str(path).replace(old_version, new_version)
        chunks.extend(encoded_entry(filename, prepare(path.name).read_bytes(), 0o100644, inode))
        inode += 1


pos = 0
chunks = []
while cpio[pos:pos + 6] == b"070701":
    header = cpio[pos:pos + 110]
    data_size = int(header[54:62], 16)
    name_size = int(header[94:102], 16)
    filename = cpio[pos + 110:pos + 110 + name_size - 1]
    start = (pos + 110 + name_size + 3) & ~3
    data = cpio[start:start + data_size]
    pos = (start + data_size + 3) & ~3
    if filename.endswith(b".ko"):
        data = prepare(Path(filename.decode()).name).read_bytes()
    elif filename.startswith(f"usr/lib/modules/{old_version}/modules.".encode()):
        data = metadata[Path(filename.decode()).name]
    elif filename in (b"init", b"./init"):
        data = data.replace(old_version.encode(), new_version.encode())
        subprocess.run(["sh", "-n"], input=data, check=True)
    filename = filename.replace(old_version.encode(), new_version.encode()) + b"\0"
    header = header[:54] + f"{len(data):08x}".encode() + header[62:94] + f"{len(filename):08x}".encode() + header[102:]
    if filename == b"TRAILER!!!\0":
        append_extra_entries(chunks)
        chunks.extend([pad(header + filename), pad(data)])
        break
    chunks.extend([pad(header + filename), pad(data)])
else:
    raise ValueError("Missing CPIO trailer")
updated = b"".join(chunks)
recompressed = subprocess.run(["libdeflate-gzip", "-12", "-c"], input=updated, check=True, capture_output=True).stdout
image = built_boot.read_bytes()
first, last = modtools["kernel_range"](image)
offset, capacity, _ = modtools["member"](image[first:last])
assert len(recompressed) <= capacity, (len(recompressed), capacity)
lo = first + offset
hi = lo + capacity
out = image[:lo] + recompressed + bytes(capacity - len(recompressed)) + image[hi:]
assert len(out) == len(source) == len(image) == 100663296
assert modtools["member"](out[first:last])[2] == updated
out_boot.write_bytes(out)
print(f"Runtime modules: {len(paths) + 3}; initramfs re-compressed {len(recompressed)}/{capacity}")
print(f"{hashlib.sha256(out).hexdigest()} {out_boot}")
