#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
#
# Builds what the one-line installer downloads for a release:
#
#   scripts/release-bundle.sh <tag> <outdir>
#
# writes into <outdir>
#   install.sh                  deploy/install.sh with the tag stamped in
#   aicc-deploy-<tag>.tar.gz    the files the stack mounts and reads, with
#                               compose.release.yml stamped with the tag
#   checksums.txt               sha256 of both, in `sha256sum -c` format
#
# The archive is reproducible: the same tree and tag give the same bytes (GNU
# tar with sorted names, a fixed mtime and owner, and gzip -n). On macOS that
# needs gtar (brew install gnu-tar); bsdtar cannot sort or fix the metadata.

set -eu

die() {
    printf 'release-bundle: %s\n' "$*" >&2
    exit 1
}

[ $# -eq 2 ] || die "usage: scripts/release-bundle.sh <tag> <outdir>"
tag=$1
out=$2
case $tag in
v[0-9]*) ;;
*) die "the tag must look like v1.2.3, got '$tag'" ;;
esac
case $tag in
*[!A-Za-z0-9.+-]*) die "the tag holds a character a file name or sed cannot carry: '$tag'" ;;
esac

root=$(cd "$(dirname "$0")/.." && pwd)
deploy=$root/deploy

if tar --version 2>/dev/null | grep -q 'GNU tar'; then
    gnutar=tar
elif command -v gtar >/dev/null 2>&1; then
    gnutar=gtar
else
    die "GNU tar is needed for a reproducible archive (on macOS: brew install gnu-tar)"
fi

if command -v sha256sum >/dev/null 2>&1; then
    sha() { sha256sum "$@"; }
else
    sha() { shasum -a 256 "$@"; }
fi

mkdir -p "$out"
out=$(cd "$out" && pwd)
stage=$(mktemp -d "${TMPDIR:-/tmp}/aicc-bundle.XXXXXX")
trap 'rm -rf "$stage"' EXIT

# What the stack needs at runtime, and nothing else: the compose files, the
# settings registry, and what they mount (postgres/, sql/, freeswitch/).
# deploy/dev is a developer's switch and never ships.
for f in docker-compose.yml compose.linux.yml compose.macos.yml .env.example; do
    cp "$deploy/$f" "$stage/$f"
done
for d in postgres sql freeswitch; do
    cp -R "$deploy/$d" "$stage/$d"
done
sed "s/@TAG@/$tag/g" "$deploy/compose.release.yml.in" >"$stage/compose.release.yml"
grep -q '@TAG@' "$stage/compose.release.yml" && die "compose.release.yml still holds @TAG@"

# No AppleDouble or Finder files, whatever the checkout picked up.
find "$stage" \( -name '._*' -o -name '.DS_Store' \) -exec rm -f {} +

bundle="aicc-deploy-$tag.tar.gz"
(
    cd "$stage"
    COPYFILE_DISABLE=1 "$gnutar" --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
        --mode='u+rwX,go+rX,go-w' --format=gnu -cf - .
) | gzip -n -9 >"$out/$bundle"

sed "s/@RELEASE_TAG@/$tag/g" "$deploy/install.sh" >"$out/install.sh"
grep -q "^AICC_RELEASE='$tag'\$" "$out/install.sh" || die "install.sh was not stamped with $tag"

(cd "$out" && sha install.sh "$bundle" >checksums.txt)
printf 'release-bundle: %s\n' "$out/install.sh" "$out/$bundle" "$out/checksums.txt"
