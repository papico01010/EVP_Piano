"""
main.py - 진입점
pygame / mediapipe / cv2 초기화 후 shared.init_shared()를 호출하고
게임 루프를 시작합니다.
"""
import sys

import cv2
import pygame
import mediapipe as mp

# ── 1. pygame / mixer 초기화 ─────────────────────────────────────────
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.init()
pygame.mixer.set_num_channels(64)

# ── 2. shared 모듈 import (pygame.init() 이후여야 font 초기화 가능) ──
import shared

# ── 3. 화면 생성 ──────────────────────────────────────────────────────
_flags  = pygame.FULLSCREEN if shared.CONFIG["fullscreen_default"] else 0
_screen = pygame.display.set_mode(shared.CONFIG["win_size"], _flags)
pygame.display.set_caption("EVP - 감정 피아노")
_clock  = pygame.time.Clock()

# ── 4. MediaPipe Hands 초기화 ─────────────────────────────────────────
_mp_hands = mp.solutions.hands
_hands    = _mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6,
)

# ── 5. 카메라 초기화 ──────────────────────────────────────────────────
_cam = cv2.VideoCapture(shared.CONFIG["camera_index"])
try:
    _w, _h = shared.CONFIG["camera_size"]
    _cam.set(cv2.CAP_PROP_FRAME_WIDTH,  _w)
    _cam.set(cv2.CAP_PROP_FRAME_HEIGHT, _h)
    _cam.set(cv2.CAP_PROP_FPS,          shared.CONFIG["camera_fps"])
except Exception:
    pass

# ── 6. 공유 상태 초기화 ───────────────────────────────────────────────
shared.init_shared(_screen, _clock, _hands, _cam)

# ── 7. 피아노 레이아웃 초기화 ─────────────────────────────────────────
import ui
ui._init_piano_layout()

# ── 8. 버튼 이미지 로드 ───────────────────────────────────────────────
ui.load_button_image_pair("yes",  "assets/ui/yes_normal.png",  "assets/ui/yes_active.png")
ui.load_button_image_pair("no",   "assets/ui/no_normal.png",   "assets/ui/no_active.png")
ui.load_button_image_pair("mode_free",
    "assets/ui/mode_free_normal.png",      "assets/ui/mode_free_active.png")
ui.load_button_image_pair("mode_follow",
    "assets/ui/mode_follow_normal.png",    "assets/ui/mode_follow_active.png")
ui.load_button_image_pair("mode_challenge",
    "assets/ui/mode_challenge_normal.png", "assets/ui/mode_challenge_active.png")

# ── 9. 게임 모드 이미지 캐시 로드 ────────────────────────────────────
import game_modes
game_modes._load_image_cache()

# ── 10. 피아노 프로필 생성 ────────────────────────────────────────────
PROFILES = ui.make_profiles()
CUR      = {"piano": PROFILES["easy"]}


# ── 메인 함수 ─────────────────────────────────────────────────────────
def main():
    while True:
        game_modes.welcome_screen()
        CUR["piano"] = PROFILES["easy"]
        ret = game_modes.mode_select_and_run()
        if ret == "BACK_TO_DIFFICULTY":
            continue


if __name__ == "__main__":
    try:
        pygame.display.flip()
        main()
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit()
