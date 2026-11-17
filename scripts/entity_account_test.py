#!/usr/bin/env python3
"""Test native Entity account transitions with private fixture data only."""
import os
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import shlex
import subprocess
import time
import threading
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
ZIRAN = os.environ.get('ZIRAN_BIN', str(ROOT / 'scripts/ziran.sh'))
ENV = {key: value for key, value in os.environ.items()
       if key not in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS')}

def package(name):
    return Path(subprocess.check_output([ZIRAN, 'pkg', 'path', name], cwd=ROOT, text=True).strip())

std_root = package('ziran')
monocypher = package('monocypher')
output = ROOT / 'build/entity-account-test'
output.mkdir(parents=True, exist_ok=True)
generated = output / 'generated'
shutil.rmtree(generated, ignore_errors=True)
subprocess.run([ZIRAN, 'build', '--project', '--root', str(ROOT), '--define', 'PLATFORM_DESKTOP',
                '--bind-host', 'entity_account_test', '--target=c',
                '--entry', 'entity_account_test:Check', '-o', str(generated),
                'tests/entity_account_test.zi'], cwd=ROOT, env=ENV, check=True)
(generated / 'main.c').write_text('#include "tests/entity_account_test.h"\n#include <stdio.h>\n#include <string.h>\n'
    'int main(void) { int result = Check(); if (result) fprintf(stderr, "Entity account fixture %d failed\\n", result); return result != 0; }\n')
executable = output / 'test'
desktop_libraries = shlex.split(subprocess.check_output(
    ['pkg-config', '--libs', 'gtk+-3.0', 'x11'], text=True, env=ENV))
subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-ffunction-sections', '-fdata-sections',
                '-Wl,--gc-sections', f'-I{std_root / "include"}', f'-I{generated}', f'-I{monocypher / "src"}',
                *map(str, generated.rglob('*.c')), str(monocypher / 'src/monocypher.c'),
                str(monocypher / 'src/optional/monocypher-ed25519.c'),
                str(ROOT / 'build/liboqs/lib/liboqs.a'), *desktop_libraries,
                '-l:libcurl.so.4', '-lpthread', '-lm', '-o', str(executable)], check=True, env=ENV)
data = output / 'data'
shutil.rmtree(data, ignore_errors=True)
ENV.update(WERK_DATA=str(data), ENTITY_DATA=str(data / 'entity'), XDG_CACHE_HOME=str(output / 'cache'))
requests = []
fixture_errors = []


class PictureNode(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path)
        # The real management pump also checks backup availability. Keep
        # that independent request in the fixture instead of bypassing it.
        if path.path == '/api/v1/account/backup':
            requests.append('backup-status')
            self.reply({'stored': False})
            return
        if path.path == '/api/v1/account-backup/methods':
            requests.append('sign-in-methods')
            self.reply({})
            return
        owner = parse_qs(path.query).get('user_id', [''])[0]
        if path.path != '/api/v1/sync/challenge' or len(owner) != 64:
            fixture_errors.append('Unexpected challenge route or identity length')
            self.send_error(400)
            return
        requests.append('challenge')
        self.reply({'nonce': '0' * 64})

    def do_POST(self):
        assert self.path == '/api/v1/sync/login'
        assert self.headers.get('X-Daochi-User') and self.headers.get('X-Daochi-Signature')
        body = self.rfile.read(int(self.headers['Content-Length']))
        assert isinstance(json.loads(body), dict)
        requests.append('login')
        self.reply({'auth_token': 'private-fixture-token', 'expires_in_seconds': 3600,
                    'server_time': int(time.time()), 'profile_icon': 128})


with ThreadingHTTPServer(('127.0.0.1', 0), PictureNode) as node:
    thread = threading.Thread(target=node.serve_forever, daemon=True)
    thread.start()
    try:
        subprocess.run([str(executable)], check=True, env=dict(
            ENV, WERK_TEST_PICTURE_SERVER=f'http://127.0.0.1:{node.server_port}'))
    finally:
        node.shutdown()
        thread.join(timeout=5)
assert 'login' in requests and requests.index('challenge') < requests.index('login'), \
    'Background picture read did not complete the real HTTP login'
assert requests.count('challenge') >= requests.count('login')
assert not fixture_errors, fixture_errors
(output / 'picture-sync-diagnostics.json').write_text(json.dumps({
    'fixture_only': True,
    'profile_opened': False,
    'pump': 'WerkManagementPump',
    'http_routes': requests,
    'received_icon': 128,
    'local_and_shared_persistence': 'passed',
    'other_app_profile_fields': 'preserved',
}, indent=2) + '\n')
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
print('Entity: account transitions, vault retention, failed-write recovery, concurrent locking, picture readback and shared-profile preservation passed.')
