#!/usr/bin/env python3
"""Registers the werkzeug app on a Daochi node with a signed manifest, so the
node accepts Werkzeug's sealed Auth records. The publisher key signs the
manifest and is created on first use; the node's registry key approves it.

Usage: register_daochi_app.py NODE_URL PUBLISHER_PEM REGISTRY_PEM
           [--dry-run] [--new-registry] [--registry-public]
"""
import json, os, sys, urllib.request, urllib.error
from hashlib import sha256
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

node, publisher_path, registry_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
dry = '--dry-run' in sys.argv

def load_or_create(path, create):
    if not path.exists():
        if not create:
            sys.exit(f'missing key {path}')
        key = Ed25519PrivateKey.generate()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    return serialization.load_pem_private_key(path.read_bytes(), password=None)

def raw_public(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

publisher = load_or_create(publisher_path, True)
registry = load_or_create(registry_path, '--new-registry' in sys.argv)
collection = 'private.werkzeug.v1.auth'
# Daochi signs json.Marshal of its normalized AppManifest: struct field order,
# omitempty fields left out, each collection carrying the app id.
manifest = {
    'manifest_version': 1,
    'manifest_sequence': 1,
    'app_id': 'werkzeug',
    'display_name': 'Werkzeug',
    'description': 'Encrypted Werkzeug Auth entries.',
    'homepage_url': 'https://pass.waozi.xyz/',
    'source_url': 'https://github.com/waozixyz/pass',
    'status': 'active',
    'app_schema_version': 1,
    'min_supported_client_version': '0.3.0',
    'current_client_version': '0.3.0',
    'compatibility_until': '2027-09-01',
    'keys': [{'key_id': 'werkzeug-2026-10', 'algorithm': 'ed25519', 'public_key': raw_public(publisher),
              'purpose': 'signing', 'status': 'active'}],
    'collections': [{'app_id': 'werkzeug', 'collection_prefix': collection, 'visibility': 'private',
                     'schema_version': 1, 'description': 'Encrypted Auth entries.'}],
    'capabilities': ['sync', 'encrypted-records'],
    'features': [{'id': 'sync.private_records', 'collections': [collection], 'requires_signed_tx': True}],
}
encoded = json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode()
body = {
    'manifest': manifest,
    'manifest_signature': publisher.sign(b'daochi-app-manifest-v1\n' + encoded).hex(),
    'approval_signature': registry.sign(
        f'daochi-app-approval-v1\nwerkzeug\n{sha256(encoded).hexdigest()}\n'.encode()).hex(),
}
if '--registry-public' in sys.argv:
    print(raw_public(registry))
    sys.exit(0)
print('manifest sha256', sha256(encoded).hexdigest())
if dry:
    sys.exit(0)
request = urllib.request.Request(node + '/api/v1/apps/register-signed',
                                 data=json.dumps(body, separators=(',', ':')).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': 'werkzeug-register/1'})
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.status, response.read(2000).decode())
except urllib.error.HTTPError as error:
    print(error.code, error.read(2000).decode())
    sys.exit(1)
