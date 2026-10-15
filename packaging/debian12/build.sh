#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export GOFLAGS='-p=2'
export GOMAXPROCS=2
export NODE_OPTIONS=--max-old-space-size=4096
export npm_config_fetch_retries=5
export npm_config_fetch_retry_mintimeout=2000
export npm_config_fetch_retry_maxtimeout=20000

test "$(dpkg --print-architecture)" = amd64
. /etc/os-release
test "$ID" = debian && test "$VERSION_ID" = 12
git config --global --add safe.directory /source
mkdir -p /build/NAC /out
git -C /source archive HEAD | tar -xf - -C /build/NAC
cd /build/NAC
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(git -C /source show -s --format=%ct HEAD)
base_version=$(dpkg-parsechangelog -S Version)
version="${base_version}+nac20.${NAC20_BUILD_NUMBER}"

node --version
npm --version
go version
apt-get update
apt-get install -y --no-install-recommends python3-distutils

# Build the actual administration UI; do not package a source-only frontend.
(
  cd html/pfappserver/root
  for attempt in 1 2 3; do
    if npm ci --no-audit --no-fund; then break; fi
    if [[ "$attempt" == 3 ]]; then
      cp /root/.npm/_logs/*debug*.log /out/ 2>/dev/null || true
      exit 1
    fi
    echo "npm download interrupted; retrying ($attempt/3)."
    sleep 3
  done
  npm run build > /out/frontend-build.log 2>&1 || { tail -n 80 /out/frontend-build.log; exit 1; }
  rm -rf node_modules
)
test -s html/pfappserver/root/dist/index.html
test -s html/pfappserver/root/dist/nac20.svg
node addons/dev-helpers/generate-nac20-installation-guide.cjs --check
python3 t/nac20-localization.py

# The existing service images are publicly distributed under latest. The custom
# HTML is mounted from the installed NAC20 package by nac20.env.defaults.
printf 'TAG_OR_BRANCH_NAME=latest\n' > conf/build_id
printf '%s\n' "$NAC20_COMMIT" > conf/git_commit_id
DEBFULLNAME='NAC20 packaging' DEBEMAIL='23178503+lehuunghi@users.noreply.github.com' \
  dch --newversion "$version" --distribution bookworm "NAC20 build from ${NAC20_COMMIT}."

# Preserve Debian's split package layout, compiled Go/C programs, maintainer
# scripts, dependencies and systemd units rather than inventing a partial .deb.
dpkg-buildpackage --build=binary --no-sign

bundle=/out/nac20-debian12-amd64-online
mkdir -p "$bundle/server" "$bundle/connector" "$bundle/connector-ad" "$bundle/docs" "$bundle/keys"
test -s /etc/apt/keyrings/packetfence.gpg
cp /etc/apt/keyrings/packetfence.gpg "$bundle/keys/packetfence.gpg"
curl --fail --show-error --location https://download.docker.com/linux/debian/gpg -o "$bundle/keys/docker.asc"
for package in /build/*.deb; do
  name=$(dpkg-deb --field "$package" Package)
  case "$name" in
    packetfence|packetfence-pfcmd-suid|packetfence-ntlm-wrapper|packetfence-config|packetfence-redis-cache|packetfence-golang-daemon|packetfence-archive-keyring|packetfence-upgrade)
      cp "$package" "$bundle/server/" ;;
    packetfence-pfconnector-remote) cp "$package" "$bundle/connector/" ;;
    packetfence-ntlm-auth-api-remote|packetfence-ntlm-auth-join-remote) cp "$package" "$bundle/connector-ad/" ;;
  esac
done
cp packaging/debian12/install.sh "$bundle/install.sh"
cp packaging/debian12/README_VI.md "$bundle/README_VI.md"
cp docs/NAC20_CAI_DAT.md "$bundle/docs/"
cp COPYING "$bundle/LICENSE"
printf '%s\n' "${base_version%.*}" > "$bundle/DEPENDENCY_SERIES"
chmod 755 "$bundle/install.sh"
python3 packaging/debian12/verify.py "$bundle" "$NAC20_COMMIT" "$version"
cp "$bundle/BUILDINFO.json" /out/BUILDINFO.json
(
  cd "$bundle"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
tar -C /out -czf /out/nac20-debian12-amd64-online.tar.gz nac20-debian12-amd64-online
cd /out
sha256sum nac20-debian12-amd64-online.tar.gz BUILDINFO.json > SHA256SUMS
echo 'NAC20 installation bundle created.'
