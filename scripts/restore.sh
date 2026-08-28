#!/bin/sh
set -eu
[ $# -eq 1 ] || { echo "Kullanım: $0 backups/YYYYMMDD-HHMMSS"; exit 1; }
[ -f .env ] && set -a && . ./.env && set +a; SRC=$1
[ -f "$SRC/database.dump" ] && [ -f "$SRC/media.tar.gz" ] || { echo "Eksik yedek"; exit 1; }
docker compose exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
docker compose exec -T db createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner < "$SRC/database.dump"
docker compose run --rm --no-deps -v "$(pwd)/$SRC:/backup:ro" web sh -c 'rm -rf /app/media/* && tar xzf /backup/media.tar.gz -C /app'
echo "Geri yükleme tamamlandı."
