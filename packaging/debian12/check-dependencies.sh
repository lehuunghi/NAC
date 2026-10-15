#!/bin/bash
# Run only in a fresh disposable Debian 12 container. No services are installed.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
bundle=/bundle/nac20-debian12-amd64-online
bash "$bundle/install.sh" server --check
bash "$bundle/install.sh" connector --check
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
