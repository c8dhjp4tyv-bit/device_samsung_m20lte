#!/usr/bin/env python3
"""Host-only startup tests. Usage: python3 -I test-crypto-start.py FIXTURE_DIR
All command/device interactions are mocked; no phone access or mounts occur.
"""
from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
tree = Path(__file__).resolve().parent.parent
root = tree / 'recovery/root'
fixtures = Path(sys.argv[1]).resolve()
fixtures.mkdir(parents=True, exist_ok=True)
manifest = ET.parse(root / 'vendor/etc/vintf/manifest.xml').getroot()
assert manifest.attrib['type'] == 'device'
assert {h.findtext('name') for h in manifest.findall('hal')} >= {
    'android.hardware.keymaster', 'android.hardware.gatekeeper'}
rc = (root / 'init.recovery.crypto.rc').read_text()
assert 'on early-init\n    setprop ro.product.first_api_level 27' in rc
assert 'ro.product.first_api_level=27' not in (tree / 'device.mk').read_text()
service = (root / 'init.recovery.service.rc').read_text()
assert 'import /init.recovery.exynos7904.rc' not in service
assert 'service recovery /system/bin/sh /system/bin/m20lte-recovery-start' in service
assert '    interface ' not in rc
print('PASS base manifest, early-init property and single device init import')
board = (tree / 'BoardConfig.mk').read_text()
assert 'TWRP_INCLUDE_LOGCAT := true' in board
assert 'TARGET_USES_LOGD := true' in board
assert not (root / 'init.recovery.logd.rc').exists(), 'empty override would mask generated logd rc'
assert 'on late-init\n    start m20lte-crypto-logcat' in rc
assert 'service m20lte-crypto-logcat /system/bin/logcat -b all' in rc
assert '-f /tmp/m20lte-crypto-logcat.txt -r 2048 -n 2' in rc
assert 'keystore2-km-compat-diagnostics.patch' in (tree / '.github/workflows/build.yml').read_text()
print('PASS diagnostic flags, generated logd rc and bounded RAM log capture')

for case in ['ready', 'gate_failure', 'not_registered']:
    d = fixtures / case
    b = d / 'bin'
    b.mkdir(parents=True, exist_ok=True)
    uptime = d / 'uptime'
    uptime.write_text('100.00 0\n')
    calls = d / 'calls'
    calls.write_text('')
    commands = {
        'getprop': '''case "$1" in
 vendor.m20lte.crypto.error) [ "$CASE" != gate_failure ] || printf '%s\\n' installed_spl_mismatch;;
 vendor.m20lte.crypto.checked) printf '1\\n';;
 vendor.sys.mobicoredaemon.enable) printf 'true\\n';;
esac
''',
        'setprop': 'printf "setprop %s %s\\n" "$1" "$2" >> "$CALLS"\n',
        'timeout': 'shift\nexec "$@"\n',
        'm20lte-crypto-ready': '''printf 'probe\\n' >> "$CALLS"
[ "$CASE" = ready ]
''',
        'sleep': 'printf "200.00 0\\n" > "$UPTIME"\n',
        'recovery': 'printf "recovery\\n" >> "$CALLS"\n',
    }
    for name, body in commands.items():
        p = b / name
        p.write_text('#!/bin/sh\n' + body)
        p.chmod(0o755)
    text = (root / 'system/bin/m20lte-recovery-start').read_text()
    text = text.replace('PATH=/system/bin:/sbin', 'PATH=' + str(b))
    text = text.replace('/system/bin/', str(b) + '/')
    text = text.replace('/tmp/m20lte-crypto-startup.log', str(d / 'startup.log'))
    text = text.replace('/proc/uptime', str(uptime))
    script = d / 'start.sh'
    script.write_text(text)
    env = dict(os.environ, CASE=case, CALLS=str(calls), UPTIME=str(uptime))
    result = subprocess.run(['/bin/sh', str(script)], env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, (case, result.stderr)
    events = calls.read_text().splitlines()
    assert events[-1] == 'recovery', events
    if case == 'ready':
        assert events.index('probe') < events.index('setprop vendor.m20lte.crypto.ready 1') < events.index('recovery')
        assert 'setprop of_skip_fbe_decryption false' in events
        assert 'setprop of_skip_fbe_decryption true' not in events
    else:
        assert 'setprop of_skip_fbe_decryption true' in events
        assert 'setprop vendor.m20lte.crypto.ready 1' not in events
        if case == 'gate_failure':
            assert 'probe' not in events
    print('PASS startup ' + case)
