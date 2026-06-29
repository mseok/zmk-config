#!/usr/bin/env bash
#
# flash-corne — fetch the latest CI firmware and flash Corne halves over UF2 (nice!nano v2).
#
# Usage:
#   flash.sh download            # download latest successful build's .uf2 into the cache
#   flash.sh flash <left|right>  # wait for NICENANO, copy that half's .uf2, verify reboot
#   flash.sh both                # flash left then right (prompts between halves)
#   flash.sh status              # show what's cached vs the latest build
#
# Env:
#   CORNE_REPO   GitHub repo            (default: mseok/zmk-config)
#   WAIT_SECS    seconds to wait for NICENANO per half (default: 90)
#
set -euo pipefail

REPO="${CORNE_REPO:-mseok/zmk-config}"
WORKFLOW="build.yml"
BRANCH="main"
WAIT_SECS="${WAIT_SECS:-90}"
CACHE="${HOME}/.cache/corne-fw"
VOL="/Volumes/NICENANO"

err()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m%s\033[0m\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { err "필요한 명령 '$1' 가 없습니다."; exit 1; }; }

latest_run_id() {
  gh -R "$REPO" run list --workflow "$WORKFLOW" --branch "$BRANCH" \
     --status success --limit 1 --json databaseId --jq '.[0].databaseId'
}

cmd_download() {
  need gh
  info "최신 성공 빌드 조회 중 ($REPO / $WORKFLOW @ $BRANCH)..."
  local rid; rid="$(latest_run_id)"
  [ -n "$rid" ] || { err "성공한 빌드를 찾지 못했습니다."; exit 1; }
  gh -R "$REPO" run view "$rid" --json displayTitle,headSha,createdAt \
     --jq '"  빌드: " + .displayTitle + "  (" + .headSha[0:7] + ", " + .createdAt + ")"'
  local tmp; tmp="$(mktemp -d)"
  info "아티팩트 다운로드 중 (run $rid)..."
  gh -R "$REPO" run download "$rid" -D "$tmp" >/dev/null
  mkdir -p "$CACHE"
  # Artifact .uf2 names carry the full shield list (e.g.
  # "corne_left nice_view_adapter nice_view_gem-nice_nano__zmk-zmk.uf2"),
  # so match a prefix glob — NOT 'corne_left-*' (the char after corne_left is a space).
  local l r
  l="$(find "$tmp" -name 'corne_left*.uf2'  | head -1)"
  r="$(find "$tmp" -name 'corne_right*.uf2' | head -1)"
  # Fail loudly instead of silently keeping a stale cached .uf2.
  [ -n "$l" ] || { err "corne_left*.uf2 아티팩트를 못 찾음 (빌드 산출물 파일명 규칙 변경?). 캐시를 갱신하지 않았습니다."; exit 1; }
  [ -n "$r" ] || { err "corne_right*.uf2 아티팩트를 못 찾음 (빌드 산출물 파일명 규칙 변경?). 캐시를 갱신하지 않았습니다."; exit 1; }
  cp "$l" "$CACHE/corne_left.uf2"
  cp "$r" "$CACHE/corne_right.uf2"
  echo "$rid" > "$CACHE/run_id"
  rm -rf "$tmp"
  ok "펌웨어 준비 완료 → $CACHE"
  ls -la "$CACHE"/*.uf2 2>/dev/null || { err "uf2 파일을 찾지 못했습니다."; exit 1; }
}

wait_for_nicenano() {
  info "NICENANO(부트로더) 대기 중... 해당 half를 부트로더로 진입시키세요 (부트로더 키 또는 리셋 더블탭). 최대 ${WAIT_SECS}s"
  local n=$(( WAIT_SECS * 2 ))
  for ((i=0; i<n; i++)); do
    [ -d "$VOL" ] && { ok "NICENANO 감지됨."; return 0; }
    sleep 0.5
  done
  err "시간 초과: NICENANO 가 나타나지 않았습니다."
  return 1
}

wait_for_unmount() {
  for ((i=0; i<40; i++)); do
    [ -d "$VOL" ] || return 0
    sleep 0.5
  done
  return 1
}

cmd_flash() {
  local half="${1:-}"
  case "$half" in left|right) ;; *) err "사용법: flash.sh flash <left|right>"; exit 2 ;; esac
  local uf2="$CACHE/corne_${half}.uf2"
  [ -f "$uf2" ] || { err "$uf2 없음 — 먼저 'flash.sh download' 를 실행하세요."; exit 1; }
  wait_for_nicenano || exit 1
  info "$half half 플래시 중..."
  # -X 로 xattr 복사를 건너뛴다(안 그러면 macOS 가 FAT NICENANO 볼륨에 xattr 을
  # 쓰려다 'Device not configured' 로 실패하면서 페이로드 전송까지 막는다). 또한
  # 대상 파일명을 짧은 8.3(FW.UF2)으로 고정한다: 최신 macOS 의 fskit FAT 드라이버가
  # 일부 구형 부트로더 볼륨에서 긴 파일명(corne_left.uf2) 생성을 'Permission denied'
  # 로 거부하는 사례가 있어서다. UF2 부트로더는 파일명과 무관하게 .uf2 를 받는다.
  #
  # 추가로 fskit 은 볼륨이 read-write 인데도 '첫' 쓰기를 가끔 'Permission denied' 로
  # 거부했다가 곧바로 재시도하면 통과하는 간헐 버그가 있다(일시적/경쟁 상태). 그래서
  # cp 를 몇 번 재시도한다. set -euo 환경에서는 cp 실패가 스크립트를 즉시 끝내므로,
  # if 로 감싸 실패를 면제시키고(루프 계속) 6 회 모두 실패했을 때만 종료한다.
  local copied=0
  for attempt in 1 2 3 4 5 6; do
    if cp -X "$uf2" "$VOL/FW.UF2" 2>/dev/null; then copied=1; break; fi
    info "  복사가 거부됨(fskit 간헐) — 재시도 ${attempt}/6..."
    sleep 1
  done
  [ "$copied" = 1 ] || { err "복사 실패: $VOL 에 6회 모두 거부됨. 케이블/부트로더 재진입 후 다시 시도하세요."; exit 2; }
  if wait_for_unmount; then
    ok "✅ $half half 플래시 완료 — 보드 재부팅 중."
  else
    err "⚠️ 복사 후에도 NICENANO 가 남아있습니다. 플래시가 안 됐을 수 있어요."
    exit 2
  fi
}

cmd_both() {
  info "왼쪽부터 진행합니다."
  cmd_flash left
  info "이제 오른쪽 half 를 부트로더로 진입시키세요."
  cmd_flash right
  ok "양쪽 완료."
}

cmd_status() {
  if [ -f "$CACHE/run_id" ]; then
    echo "캐시된 빌드 run: $(cat "$CACHE/run_id")"
    ls -la "$CACHE"/*.uf2 2>/dev/null || true
  else
    echo "캐시 없음 — 'flash.sh download' 를 먼저 실행하세요."
  fi
  need gh
  echo "최신 성공 빌드 run: $(latest_run_id)"
}

case "${1:-}" in
  download) cmd_download ;;
  flash)    shift; cmd_flash "$@" ;;
  both)     cmd_both ;;
  status)   cmd_status ;;
  *) cat >&2 <<'EOF'
사용법:
  flash.sh download            최신 성공 빌드의 .uf2 다운로드(캐시)
  flash.sh flash <left|right>  NICENANO 대기 → 해당 half 복사 → 재부팅 검증
  flash.sh both                왼쪽 → 오른쪽 순서로 플래시
  flash.sh status              캐시 / 최신 빌드 상태
EOF
     exit 2 ;;
esac
