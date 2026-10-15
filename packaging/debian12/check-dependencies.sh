#!/bin/bash
# Run only in a fresh disposable Debian 12 container. No services are installed.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
bundle=/bundle/nac20-debian12-amd64-online
bash "$bundle/install.sh" server --check
bash "$bundle/install.sh" connector --check
# Guard against the fresh installer overwriting either an existing server or
# Connector when the other package is absent (dpkg-query then exits non-zero).
testbin=$(mktemp -d)
mkdir -p /run/systemd/system
cat > "$testbin/dpkg-query" <<'SH'
#!/bin/bash
if [[ "${!#}" == "$NAC20_TEST_INSTALLED" ]]; then printf installed; else exit 1; fi
SH
cat > "$testbin/apt-get" <<'SH'
#!/bin/bash
echo 'Unexpected APT call during existing-installation test' >&2
exit 97
SH
chmod +x "$testbin/dpkg-query" "$testbin/apt-get"
for existing in packetfence packetfence-pfconnector-remote; do
  if PATH="$testbin:$PATH" NAC20_TEST_INSTALLED="$existing" bash "$bundle/install.sh" server --install > /tmp/nac20-existing.log 2>&1; then
    echo 'Fresh installer incorrectly accepted an existing installation.' >&2
    exit 1
  fi
  grep -q 'existing or incomplete installation' /tmp/nac20-existing.log
done
rmdir /run/systemd/system
echo 'PASS: fresh installer rejects an existing server or Connector.'
apt-get update
apt-get install -y --no-install-recommends ca-certificates gnupg
install -d -m0755 /etc/apt/keyrings
cp "$bundle/keys/packetfence.gpg" /etc/apt/keyrings/nac20-platform.gpg
gpg --batch --dearmor -o /etc/apt/keyrings/nac20-docker.gpg "$bundle/keys/docker.asc"
read -r series < "$bundle/DEPENDENCY_SERIES"
cat > /etc/apt/sources.list.d/nac20-dependencies.list <<EOF
deb [signed-by=/etc/apt/keyrings/nac20-platform.gpg] https://inverse.ca/downloads/PacketFence/debian/$series bookworm bookworm
deb [arch=amd64 signed-by=/etc/apt/keyrings/nac20-docker.gpg] https://download.docker.com/linux/debian bookworm stable
EOF
apt-get update
apt-get --simulate install "$bundle/server/"*.deb
apt-get --simulate install "$bundle/connector/"*.deb
echo 'PASS: APT can resolve both server and Connector package dependencies on fresh Debian 12.'
