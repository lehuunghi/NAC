#!/bin/bash
# Online installer for the verified NAC20 Debian 12 bundle.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
bundle=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
role=${1:-}
action=${2:---check}
if [[ "$role" != server && "$role" != connector ]] || [[ "$action" != --check && "$action" != --install ]]; then
  echo 'Usage: sudo bash install.sh {server|connector} {--check|--install}' >&2
  exit 2
fi
. /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 12 ]] || { echo 'Requires Debian 12.' >&2; exit 1; }
[[ "$(dpkg --print-architecture)" == amd64 ]] || { echo 'Requires amd64/x86_64.' >&2; exit 1; }
cd "$bundle"
sha256sum --check --strict SHA256SUMS
shopt -s nullglob
packages=("$bundle/$role/"*.deb)
((${#packages[@]} > 0)) || { echo 'Installation packages missing.' >&2; exit 1; }
for package in "${packages[@]}"; do dpkg-deb --field "$package" Package Version Architecture; done
if [[ "$action" == --check ]]; then
  echo 'Bundle checks passed. This does not install services or verify network operation.'
  exit 0
fi
[[ "$EUID" == 0 ]] || { echo 'Run the installer as root.' >&2; exit 1; }
[[ -d /run/systemd/system ]] || { echo 'Requires a Debian host booted with systemd, not a build container.' >&2; exit 1; }
if dpkg-query -W -f='${db:Status-Status}\n' packetfence packetfence-pfconnector-remote 2>/dev/null | grep -q '^installed$'; then
  echo 'An existing installation was detected. Use a tested upgrade procedure and backup instead of the fresh installer.' >&2
  exit 1
fi
read -r series < "$bundle/DEPENDENCY_SERIES"
[[ "$series" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Invalid dependency series.' >&2; exit 1; }
echo 'Installing NAC20 on a dedicated Debian 12 host. Internet access is required for dependencies and service images.'
apt-get update
apt-get install -y ca-certificates gnupg curl locales-all
install -d -m 0755 /etc/apt/keyrings
install -m 0644 "$bundle/keys/packetfence.gpg" /etc/apt/keyrings/nac20-platform.gpg
gpg --batch --yes --dearmor -o /etc/apt/keyrings/nac20-docker.gpg "$bundle/keys/docker.asc"
chmod 0644 /etc/apt/keyrings/nac20-docker.gpg
cat > /etc/apt/sources.list.d/nac20-dependencies.list <<EOF
deb [signed-by=/etc/apt/keyrings/nac20-platform.gpg] https://inverse.ca/downloads/PacketFence/debian/$series bookworm bookworm
deb [arch=amd64 signed-by=/etc/apt/keyrings/nac20-docker.gpg] https://download.docker.com/linux/debian bookworm stable
EOF
apt-get update
# Let APT verify dependency resolution before installing the local package set.
apt-get --simulate install "${packages[@]}"
apt-get install -y "${packages[@]}"
if [[ "$role" == server ]]; then
  echo 'NAC20 server installed. Open https://YOUR_NAC20_HOST:1443 to complete configuration.'
else
  echo 'Connector installed. Pair it using /usr/local/pfconnector-remote/bin/pfconnector-configure'
  echo 'Then start packetfence-pfconnector-remote-combined.service after configuring TLS and the tunnel.'
fi
