#!/bin/sh
set -eu
[ -f .env ] && set -a && . ./.env && set +a
STAMP=$(date +%Y%m%d-%H%M%S); DEST=${1:-backups/$STAMP}; mkdir -p "$DEST"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DEST/database.dump"
docker compose run --rm --no-deps -v "$(pwd)/$DEST:/backup" web tar czf /backup/media.tar.gz -C /app media
cp .env "$DEST/.env"; echo "Yedek: $DEST"
