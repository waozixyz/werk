#!/usr/bin/env python3
"""Test native Self account transitions with private fixture data only."""
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
ZIRAN = os.environ.get('ZIRAN_BIN', str(ROOT / 'scripts/ziran.sh'))
ENV = {key: value for key, value in os.environ.items()
       if key not in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS')}

def package(name):
    return Path(subprocess.check_output([ZIRAN, 'pkg', 'path', name], cwd=ROOT, text=True).strip())

std_root = package('ziran')
monocypher = package('monocypher')
output = ROOT / 'build/self-account-test'
output.mkdir(parents=True, exist_ok=True)
generated = output / 'generated'
shutil.rmtree(generated, ignore_errors=True)
subprocess.run([ZIRAN, 'build', '--project', '--root', str(ROOT), '--define', 'PLATFORM_DESKTOP', '--target=c',
                '--entry', 'self_account_test:Check', '-o', str(generated),
                'tests/self_account_test.zi'], cwd=ROOT, env=ENV, check=True)
(generated / 'main.c').write_text('#include "tests/self_account_test.h"\n#include <stdio.h>\n#include <string.h>\n'
    'int main(void) { int result = Check(); if (result) fprintf(stderr, "Self account fixture %d failed\\n", result); return result != 0; }\n')
executable = output / 'test'
subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-ffunction-sections', '-fdata-sections',
                '-Wl,--gc-sections', f'-I{std_root / "include"}', f'-I{generated}', f'-I{monocypher / "src"}',
                *map(str, generated.rglob('*.c')), str(monocypher / 'src/monocypher.c'),
                str(monocypher / 'src/optional/monocypher-ed25519.c'),
                str(ROOT / 'build/liboqs/lib/liboqs.a'), '-l:libcurl.so.4', '-lpthread', '-lm', '-o', str(executable)], check=True, env=ENV)
data = output / 'data'
shutil.rmtree(data, ignore_errors=True)
ENV.update(WERK_DATA=str(data), XDG_CACHE_HOME=str(output / 'cache'))
subprocess.run([str(executable)], check=True, env=ENV)
# A concurrent CLI reader must wait for an active GUI switch instead of
# treating its rollback journal as an interrupted transaction.
ready = data / 'account/switch/held'
ready.unlink(missing_ok=True)
writer = subprocess.Popen([str(executable)], env=dict(ENV, WERK_TEST_JOURNAL_MODE='hold'))
reader = None
try:
    deadline = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < deadline:
        assert writer.poll() is None, 'Journal writer exited before holding the lock'
        time.sleep(.02)
    assert ready.exists(), 'Journal lock fixture did not start'
    reader = subprocess.Popen([str(executable)], env=dict(ENV, WERK_TEST_JOURNAL_MODE='recover'))
    time.sleep(.2)
    assert reader.poll() is None and (data / 'account/switch/pending').exists(), 'A concurrent reader recovered an active journal'
    assert writer.wait(timeout=5) == 0 and reader.wait(timeout=5) == 0
finally:
    for process in (reader, writer):
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
ready.unlink(missing_ok=True)
for path in data.rglob('*'):
    assert path.stat().st_mode & 0o077 == 0, f'Non-private fixture path: {path.name}'
print('Self: vault retention, merge/replace, tombstones, pause choice, failed writes, interrupted-switch recovery, concurrent reader locking and logout passed.')
