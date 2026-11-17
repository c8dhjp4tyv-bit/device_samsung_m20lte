#!/usr/bin/env python3
"""Import only stock M20 crypto blobs; never copy Android 15 runtime libraries.

Usage: python3 -I scripts/import-crypto.py BUILT_VENDOR_DIR FOX_SYSTEM_LIB64_DIR
Run from a trusted directory. All destinations are inside this device tree.
The shim dependency added for Android 15 is removed from the copied helper:
Fox 12.1 exports the original sk_delete directly from libcrypto.so instead.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

TRUSTLETS = [
    'FFFFFFFF000000000000000000000001.drbin',
    'ffffffffd0000000000000000000000a.tlbin',
    'ffffffffd00000000000000000000016.tlbin',
    'ffffffffd00000000000000000000045.drbin',
    'ffffffff00000000000000000000003e.tlbin',
    '08130000000000000000000000000000.tlbin',
]
LIBRARIES = [
    'lib64/libMcClient.so',
    'lib64/libkeymaster2_mdfpp.so',
    'lib64/libkeymaster_helper_vendor.so',
    'lib64/hw/keystore.mdfpp.so',
    'lib64/hw/gatekeeper.exynos7904.so',
]

def remove_needed(blob, target):
    """Delete a DT_NEEDED entry in place, without relocating ELF contents."""
    b = bytearray(blob)
    if b[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected little-endian ELF64')
    phoff = struct.unpack_from('<Q', b, 32)[0]
    phsize, phnum = struct.unpack_from('<HH', b, 54)
    loads = []
    dynamic = None
    for i in range(phnum):
        typ, _, off, va, _, filesz, _, _ = struct.unpack_from('<IIQQQQQQ', b, phoff + phsize * i)
        if typ == 1:
            loads.append((va, off, filesz))
        elif typ == 2:
            dynamic = (off, filesz)
    if dynamic is None:
        raise ValueError('missing PT_DYNAMIC')
    off, size = dynamic
    entries = []
    for p in range(off, off + size, 16):
        tag, value = struct.unpack_from('<qQ', b, p)
        entries.append((tag, value))
        if tag == 0:
            break
    string_va = next(value for tag, value in entries if tag == 5)
    string_off = next(p + string_va - va for va, p, n in loads if va <= string_va < va + n)
    retained = []
    removed = 0
    for tag, value in entries:
        name = bytes(b[string_off + value:]).split(b'\0', 1)[0] if tag == 1 else b''
        if tag == 1 and name == target.encode():
            removed += 1
        else:
            retained.append((tag, value))
    for i, entry in enumerate(retained + [(0, 0)] * removed):
        struct.pack_into('<qQ', b, off + i * 16, *entry)
    assert len(b) == len(blob)
    return bytes(b), removed


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    vendor, foxlibs = map(Path, sys.argv[1:])
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(foxlibs / 'libcrypto.so')], text=True)
    if not any(len(p := line.split()) >= 8 and p[6] != 'UND' and p[7].split('@')[0] == 'sk_delete' for line in symbols.splitlines()):
        raise SystemExit('Fox libcrypto must export sk_delete; do not use this import on newer bases')
    tree = Path(__file__).resolve().parent.parent
    root = tree / 'recovery/root'
    paths = {s: 'vendor/' + s for s in LIBRARIES}
    paths['bin/mcDriverDaemon'] = 'system/bin/mcDriverDaemon'
    paths.update({'app/mcRegistry/' + f: 'vendor/app/mcRegistry/' + f for f in TRUSTLETS})
    for source in paths:
        if not (vendor / source).is_file():
            raise SystemExit('missing input: ' + source)
    manifest = {'firmware': 'M205FDDS9CWB2', 'target_runtime': 'Fox 12.1 / Android 12', 'files': []}
    for source, dest in sorted(paths.items()):
        blob = (vendor / source).read_bytes()
        converted = blob
        removed = 0
        if source == 'lib64/libkeymaster_helper_vendor.so':
            converted, removed = remove_needed(blob, 'libshim_keymaster.so')
        dst = root / dest
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(converted)
        dst.chmod(0o755 if '/bin/' in '/' + dest else 0o644)
        manifest['files'].append({'source': 'vendor/' + source, 'destination': 'recovery/root/' + dest,
                                  'source_sha256': hashlib.sha256(blob).hexdigest(),
                                  'sha256': hashlib.sha256(converted).hexdigest(),
                                  'removed_android15_shim_dependency': bool(removed)})
    (tree / 'crypto-blobs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Imported', len(paths), 'stock files; Android 15 runtime/HIDL binaries were not copied.')

if __name__ == '__main__':
    main()
