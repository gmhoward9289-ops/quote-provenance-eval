#!/usr/bin/env bash
# Read-only: does PyPI actually serve the version pyproject.toml claims?
#
# Channels for trust-but-anchor: git tag + GitHub release assets + PyPI + pypi env.
set -u

OWNER=gmhoward9289-ops
REPO=$OWNER/trust-but-anchor
DIST=trust-but-anchor
ROOT=$(cd "$(dirname "$0")/.." && pwd)

GRACE_MIN=${PUBLISH_DOCTOR_GRACE_MIN:-60}

VERSION=$(grep -E '^version = ' "$ROOT/pyproject.toml" | head -1 | sed -n 's/.*"\([^"]*\)".*/\1/p')
if [ -z "$VERSION" ]; then
  echo "FATAL: could not read version from pyproject.toml" >&2
  exit 2
fi

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
elif [ -x "/c/Users/gmhow/AppData/Local/Programs/Python/Python312/python.exe" ]; then
  PY="/c/Users/gmhow/AppData/Local/Programs/Python/Python312/python.exe"
elif command -v py >/dev/null 2>&1; then
  PY="py -3"
else
  PY=
fi

fails=0
pendings=0
todos=0

say()  { printf '  %-8s %-10s %s\n' "$1" "$2" "$3"; }
pass() { say PASS "$1" "$2"; }
skip() { say "--" "$1" "$2"; }
todo() { say TODO "$1" "$2"; todos=$((todos + 1)); }
pend() { say PENDING "$1" "$2"; pendings=$((pendings + 1)); }
fail() { say FAIL "$1" "$2"; fails=$((fails + 1)); }

lagging() {
  if [ "$fresh" = 1 ]; then
    pend "$1" "$2 [$why_fresh]"
  else
    fail "$1" "$2"
  fi
}

echo "trust-but-anchor publish doctor -- version $VERSION (read-only)"
echo

published=$(gh release view "v$VERSION" --repo "$REPO" --json publishedAt \
              --jq '.publishedAt' 2>/dev/null)
if [ -n "${published:-}" ]; then
  if [ -n "$PY" ]; then
    age_min=$("$PY" -c '
import datetime, sys
t = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%SZ")
t = t.replace(tzinfo=datetime.timezone.utc)
print(int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() // 60))
' "$published" 2>/dev/null)
  else
    age_min=99999
  fi
  : "${age_min:=99999}"
  if [ "$age_min" -lt "$GRACE_MIN" ]; then fresh=1; else fresh=0; fi
  why_fresh="release is ${age_min}m old, inside the ${GRACE_MIN}m window"
else
  fresh=1
  why_fresh="no v$VERSION GitHub release yet"
fi

tags=$(gh api "repos/$REPO/git/refs/tags" --jq '.[].ref' 2>/dev/null | sed 's#refs/tags/##')
latest_tag=$(printf '%s\n' "$tags" | grep -v '^$' | sed 's/^v//' | sort -V | tail -1)
if printf '%s\n' "$tags" | grep -qx "v$VERSION"; then
  pass "git tag" "v$VERSION is on the remote"
elif [ -z "${latest_tag:-}" ]; then
  todo "git tag" "no tags on $REPO yet"
elif [ "$(printf '%s\n%s\n' "$latest_tag" "$VERSION" | sort -V | tail -1)" = "$VERSION" ]; then
  pend "git tag" "newest tag is v$latest_tag, pyproject says $VERSION -- tag not cut yet"
else
  fail "git tag" "remote has v$latest_tag but pyproject says $VERSION"
fi

if [ -n "${published:-}" ]; then
  assets=$(gh release view "v$VERSION" --repo "$REPO" --json assets \
             --jq '[.assets[].name] | join(" ")' 2>/dev/null)
  want_whl="trust_but_anchor-$VERSION-py3-none-any.whl"
  want_sdist="trust_but_anchor-$VERSION.tar.gz"
  case " ${assets:-} " in
    *" $want_whl "*) pass "gh release" "v$VERSION has $want_whl" ;;
    *) lagging "gh release" "v$VERSION release missing $want_whl (assets: ${assets:-none})" ;;
  esac
  case " ${assets:-} " in
    *" $want_sdist "*) pass "gh sdist" "v$VERSION has $want_sdist" ;;
    *) lagging "gh sdist" "v$VERSION release missing $want_sdist" ;;
  esac
else
  skip "gh release" "no v$VERSION release page yet"
fi

pypi=$(curl -sf "https://pypi.org/pypi/$DIST/json" 2>/dev/null)
if [ -z "$pypi" ]; then
  todo pypi "nothing on PyPI as $DIST -- trusted publisher: $REPO release.yml environment pypi"
else
  if [ -n "$PY" ]; then
    pypi_ver=$(printf '%s' "$pypi" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null)
    names=$(printf '%s' "$pypi" | "$PY" -c 'import json,sys; print(" ".join(f["filename"] for f in json.load(sys.stdin)["urls"]))' 2>/dev/null)
  else
    pypi_ver=$(printf '%s' "$pypi" | grep -o '"version":"[^"]*"' | head -1 | cut -d'"' -f4)
    names=$(printf '%s' "$pypi" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ')
  fi
  if [ "${pypi_ver:-}" = "$VERSION" ]; then
    want_whl="trust_but_anchor-$VERSION-py3-none-any.whl"
    want_sdist="trust_but_anchor-$VERSION.tar.gz"
    case " $names " in
      *" $want_whl "*) ;;
      *) fail pypi "serves $pypi_ver but no $want_whl among: ${names:-<none>}" ;;
    esac
    case " $names " in
      *" $want_sdist "*) ;;
      *) fail pypi "serves $pypi_ver but no $want_sdist among: ${names:-<none>}" ;;
    esac
    pass pypi "pip install $DIST ($pypi_ver)"
  else
    lagging pypi "registry has ${pypi_ver:-<unparseable>}, want $VERSION -- rerun release.yml on tag v$VERSION"
  fi
fi

if [ -n "${GITHUB_ACTIONS:-}" ]; then
  skip secret "PyPI uses OIDC trusted publishing; no repo secrets to check"
else
  envs=$(gh api "repos/$REPO/environments/pypi" --jq '.name' 2>/dev/null)
  if [ "${envs:-}" = "pypi" ]; then
    pass secret "GitHub Environment pypi exists (OIDC)"
  else
    todo secret "create GitHub Environment named pypi on $REPO (Settings -> Environments)"
  fi
fi

echo
printf 'pending %d  todo %d  fail %d\n' "$pendings" "$todos" "$fails"
if [ "$fails" -ne 0 ]; then
  echo
  echo "FAIL means a channel disagrees with $VERSION and propagation is not the explanation."
  echo "Rerun the failed release job:"
  echo "  gh workflow run release.yml --repo $REPO --ref v$VERSION"
  exit 1
fi
if [ "$todos" -ne 0 ]; then
  echo "TODO items are one-time setup, not breakage."
fi
echo "Channels match $VERSION (or nothing is established yet)."
