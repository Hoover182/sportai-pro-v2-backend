#!/usr/bin/env bash
# Commitea y pushea los CSV de NBA a la rama donde corre el workflow.
# Uso: commit_sync_nba.sh "mensaje". Lo llama nba-sync.yml (por temporada
# en backfill, una vez en diario).
set -u
git config user.name "sync-bot"
git config user.email "sync-bot@users.noreply.github.com"
git add -A -- 'app/services/nba_*'   # glob: en backfill no hay cartelera
git diff --cached --quiet && { echo "Sin cambios para commitear"; exit 0; }
git commit -m "$1" || exit 1
# Otro push (p. ej. un merge de futbol) puede haber entrado mientras tanto:
# rebase y reintento. Los archivos de NBA no los toca nadie mas.
for i in 1 2 3; do
  git pull --rebase origin "$GITHUB_REF_NAME" && git push origin "HEAD:$GITHUB_REF_NAME" && exit 0
  sleep 10
done
echo "::error::No se pudo pushear el sync de NBA"
exit 1
