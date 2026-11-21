#!/bin/sh
# 组装不含 .env、.git、node_modules、.venv、用户上传和报告的部署归档。
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
out=${1:-/opt/cursor/artifacts/zxd-ai-deploy.tar.gz}
test -f "$root/web/dist/index.html"
test -f "$root/admin-web/dist/index.html"
test -f "$root/.env.production.example"

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
dest="$stage/zxd-ai"
mkdir -p "$dest/data" "$dest/web" "$dest/admin-web" "$dest/deploy"

cp -a "$root/app" "$dest/app"
find "$dest/app" -depth -type d -name __pycache__ -exec rm -rf {} +
cp "$root/requirements.txt" "$root/.env.production.example" "$dest/"
cp "$root/data/shenlun_questions.json" "$root/data/kaoyan_questions.json" \
  "$root/data/sample_questions.json" "$root/data/practice_figures.json" "$dest/data/"
cp -a "$root/web/dist" "$dest/web/dist"
cp -a "$root/admin-web/dist" "$dest/admin-web/dist"
cp -a "$root/deploy/ubuntu" "$dest/deploy/ubuntu"

if find "$dest" \( -name .env -o -name 'node_modules' -o -name .venv -o -name .git -o -name 'app.db' -o -name 'app.db-*' \) | grep -q .; then
  echo "archive contains forbidden path" >&2
  find "$dest" \( -name .env -o -name node_modules -o -name .venv -o -name .git -o -name 'app.db' \) >&2
  exit 1
fi
if find "$dest" -path '*/uploads/*' -o -path '*/data/raw/*' -o -path '*/data/eval/*' | grep -q .; then
  echo "archive contains uploads or raw reports" >&2
  exit 1
fi

mkdir -p "$(dirname "$out")"
tar -C "$stage" -czf "$out" zxd-ai
echo "$out"
