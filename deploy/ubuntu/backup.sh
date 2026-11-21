#!/bin/sh
# 在线备份本服务自己的 SQLite 与上传目录。不要把目标指到其他服务的数据库。
set -eu
db=/opt/zxd-ai/data/zxd-ai.db
dest_dir=/var/backups/zxd-ai
if [ ! -f "$db" ]; then
  echo "missing $db" >&2
  exit 1
fi
install -d -o zxd-ai -g zxd-ai -m 700 "$dest_dir"
stamp=$(date +%Y%m%d-%H%M%S)
sudo -u zxd-ai sqlite3 "$db" ".backup '$dest_dir/zxd-ai-$stamp.db'"
if [ -d /opt/zxd-ai/data/uploads ]; then
  sudo -u zxd-ai tar -C /opt/zxd-ai/data -czf "$dest_dir/uploads-$stamp.tar.gz" uploads
fi
echo "$dest_dir/zxd-ai-$stamp.db"
