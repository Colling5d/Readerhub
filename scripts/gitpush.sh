#!/usr/bin/env bash
# gitpush.sh — 智能推送：本地代理可用则走代理，否则直连。
#
# 用法:
#   scripts/gitpush.sh                 # push origin 当前分支
#   scripts/gitpush.sh origin main     # 指定远端/分支
#
# 背景: 机器上曾把 GitHub 代理写死在 gitconfig 里 (127.0.0.1:7890)，
#       代理没开时会导致所有 push 失败。此脚本自动探测端口，避免再踩坑。
set -euo pipefail

REMOTE="${1:-origin}"
BRANCH="${2:-$(git rev-parse --abbrev-ref HEAD)}"
PROXY_HOST="127.0.0.1"
PROXY_PORT="${READERHUB_PROXY_PORT:-7890}"
PROXY="http://${PROXY_HOST}:${PROXY_PORT}"

# 探测代理端口是否有人监听（优先 nc，其次 bash /dev/tcp）
proxy_alive() {
  if command -v nc >/dev/null 2>&1; then
    nc -z -G 1 "$PROXY_HOST" "$PROXY_PORT" >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/${PROXY_HOST}/${PROXY_PORT}") >/dev/null 2>&1
  fi
}

echo "==> push ${REMOTE} ${BRANCH}"
if proxy_alive; then
  echo "    检测到代理 ${PROXY} 可用，走代理推送"
  HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY" ALL_PROXY="$PROXY" \
    git push "$REMOTE" "$BRANCH"
else
  echo "    未检测到代理 ${PROXY}，直连推送"
  git push "$REMOTE" "$BRANCH"
fi
