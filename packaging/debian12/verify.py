#!/usr/bin/env python3
"""Verify the installer contains real binary packages and the NAC20 interface."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

bundle = Path(sys.argv[1])
commit, version = sys.argv[2:4]
required = {
    'server': {'packetfence', 'packetfence-pfcmd-suid', 'packetfence-ntlm-wrapper',
               'packetfence-config', 'packetfence-redis-cache', 'packetfence-golang-daemon',
               'packetfence-archive-keyring', 'packetfence-upgrade'},
    'connector': {'packetfence-pfconnector-remote'},
    'connector-ad': {'packetfence-ntlm-auth-api-remote', 'packetfence-ntlm-auth-join-remote'}
}
packages = []
found = {}
for group, names in required.items():
    actual = set()
    for path in sorted((bundle / group).glob('*.deb')):
        name = subprocess.check_output(['dpkg-deb', '-f', str(path), 'Package'], text=True).strip()
        package_version = subprocess.check_output(['dpkg-deb', '-f', str(path), 'Version'], text=True).strip()
        architecture = subprocess.check_output(['dpkg-deb', '-f', str(path), 'Architecture'], text=True).strip()
        assert package_version == version, (name, package_version, version)
        assert architecture in ('all', 'amd64'), (name, architecture)
        actual.add(name)
        packages.append({'package': name, 'version': package_version, 'architecture': architecture,
                         'file': str(path.relative_to(bundle)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        with subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(path)], stdout=subprocess.PIPE) as process:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for item in archive:
                    target = item.name.removeprefix('./')
                    assert '/node_modules/' not in target and '/.git/' not in target, target
                    if target in ('usr/local/pf/conf/local_secret', 'usr/local/pf/conf/system_init_key',
                                  'usr/local/pf/conf/unified_api_system_pass'):
                        assert item.size == 0, 'A per-installation secret must not be distributed'
                    if target in (
                        'usr/local/pf/html/pfappserver/root/dist/index.html',
                        'usr/local/pf/html/pfappserver/root/dist/nac20.svg',
                        'usr/local/pf/conf/locale/vi/LC_MESSAGES/packetfence.mo',
                        'usr/local/pf/containers/.local_env',
                        'usr/local/pf/conf/build_id',
                        'usr/local/pf/bin/pfcmd',
                        'usr/local/pf/sbin/pfconnector',
                        'usr/local/pfconnector-remote/bin/pfconnector',
                    ):
                        assert item.isfile() and item.size > 0, target
                        data = archive.extractfile(item).read()
                        found[target] = data
                        if target.endswith('/pfcmd') or target.endswith('/pfconnector'):
                            assert data.startswith(b'\x7fELF'), target
            assert process.wait() == 0
    assert actual == names, (group, actual, names)

assert b'NAC20' in found['usr/local/pf/html/pfappserver/root/dist/index.html']
assert b'HTML_MOUNT=/usr/local/pf/html' in found['usr/local/pf/containers/.local_env']
assert b'TAG_OR_BRANCH_NAME=latest' in found['usr/local/pf/conf/build_id']
for path in ('usr/local/pf/html/pfappserver/root/dist/nac20.svg',
             'usr/local/pf/conf/locale/vi/LC_MESSAGES/packetfence.mo',
             'usr/local/pf/bin/pfcmd', 'usr/local/pf/sbin/pfconnector',
             'usr/local/pfconnector-remote/bin/pfconnector'):
    assert path in found, path
info = {
    'product': 'NAC20', 'company': 'Công Ty TNHH TN20', 'domain': '20.com.vn',
    'source_commit': commit, 'version': version, 'os': 'Debian 12', 'architecture': 'amd64',
    'dependency_series': '.'.join(version.split('.')[:2]),
    'builder_image': os.environ['NAC20_BUILDER_DIGEST'],
    'runtime_image_registry': 'ghcr.io/inverse-inc/packetfence', 'runtime_image_tag': 'latest',
    'installation_type': 'online', 'release_status': 'preview',
    'checks': ['Debian package metadata', 'compiled ELF programs', 'compiled NAC20 frontend',
               'Vietnamese gettext catalog', 'NAC20 HTML mount', 'no pre-generated installation secrets'],
    'not_tested': ['full systemd installation on a VPS', 'live RADIUS and MAB against network equipment'],
    'packages': packages
}
(bundle / 'BUILDINFO.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'PASS: {len(packages)} Debian packages, compiled NAC20 UI, binaries and Vietnamese catalog.')
