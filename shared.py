"""
shared.py - 전역 공유 상태 모듈
모든 모듈은 `import shared`로 이 모듈의 변수에 접근합니다.
이 모듈은 다른 프로젝트 모듈을 import하지 않습니다.
"""
import os
import glob
import pygame

# ── 디버그 플래그 ──────────────────────────────────────────────────────
DEBUG_HITBOX = {"on": False, "press": False, "hyst": False}
PRESS_DBG    = {"pip": 0.0, "dip": 0.0, "lenr": 0.0, "bend": 0.0,
                "avg": 0.0, "pressed": False, "series": []}

# ── 설정 ──────────────────────────────────────────────────────────────
CONFIG = {
    "fullscreen_default": False,
    "win_size":      (1280, 720),
    "camera_index":  0,
    "camera_size":   (1280, 720),
    "camera_fps":    30,
    "back_hold":     3.0,
    "exit_hold":     3.0,
}

# ── 화면/시계 (init_shared()에서 채워짐) ─────────────────────────────
screen: pygame.Surface = None
clock:  pygame.time.Clock = None
WIN_W: int = 1280
WIN_H: int = 720

# ── 폰트 (init_shared()에서 채워짐) ──────────────────────────────────
FONT_FILE:   str                = None
font_huge:   pygame.font.Font   = None
font_big:    pygame.font.Font   = None
font_mid:    pygame.font.Font   = None
font_small:  pygame.font.Font   = None
font_tiny:   pygame.font.Font   = None
font_micro:  pygame.font.Font   = None

# ── MediaPipe / 카메라 (init_shared()에서 채워짐) ─────────────────────
hands = None   # mp_hands.Hands 인스턴스
cam   = None   # cv2.VideoCapture 인스턴스

# ── 사운드 캐시 ───────────────────────────────────────────────────────
SND_CACHE: dict = {}

# ── 색상 팔레트 ───────────────────────────────────────────────────────
COLORS = {
    "pill_bg":      (0, 0, 0, 170),
    "pill_outline": (255, 255, 255, 210),
    "text_shadow":  (0, 0, 0),
    "ok":           (60, 220, 100),
    "warn":         (255, 200, 60),
    "crit":         (255, 80, 80),
    "accent":       (80, 160, 255),
    "banner_bg":    (0, 0, 0, 180),
    "banner_fg":    (255, 255, 255),
}

# ── 피아노 레이아웃 ───────────────────────────────────────────────────
PIANO_KEY_NOTES = [
    "C4", "Cs4", "D4", "Ds4", "E4", "F4", "Fs4", "G4", "Gs4", "A4", "As4", "B4",
    "C5", "Cs5", "D5", "Ds5", "E5", "F5", "Fs5", "G5", "Gs5", "A5", "As5", "B5",
]
PIANO_WHITE_NOTES = [
    "C4", "D4", "E4", "F4", "G4", "A4", "B4",
    "C5", "D5", "E5", "F5", "G5", "A5", "B5",
]
PIANO_BLACK_NOTES = [
    "Cs4", "Ds4", "Fs4", "Gs4", "As4",
    "Cs5", "Ds5", "Fs5", "Gs5", "As5",
]

PIANO_X: int  = None
PIANO_Y: int  = None
PIANO_W: int  = None
PIANO_H: int  = None
WHITE_W: int  = None
WHITE_H: int  = None
BLACK_W: int  = None
BLACK_H: int  = None
_piano_key_boxes: dict = {}

# ── 버튼/UI 이미지 ────────────────────────────────────────────────────
BTN_IMAGES: dict        = {}
_select_timer_imgs: dict = {}
_back_timer_imgs: dict   = {}
_exit_timer_imgs: dict   = {}
_tip_img = None

ASSETS = "assets"


# ── 폰트 헬퍼 ─────────────────────────────────────────────────────────
def _pick_font_path():
    for d in ["SB_Window_Font", "SB_Window_Font/Fonts", "SB_Window_Font/font"]:
        if os.path.isdir(d):
            files = sorted(
                glob.glob(os.path.join(d, "*.ttf")) +
                glob.glob(os.path.join(d, "*.otf"))
            )
            if files:
                return files[0]
    noto = os.path.join("Noto_Sans_KR", "NotoSansKR-VariableFont_wght.ttf")
    if os.path.exists(noto):
        return noto
    return None


def _font(size):
    try:
        return (pygame.font.Font(FONT_FILE, size)
                if FONT_FILE else pygame.font.SysFont(None, size))
    except Exception:
        return pygame.font.SysFont(None, size)


# ── init_shared: main.py에서 pygame 초기화 후 호출 ───────────────────
def init_shared(
    _screen: pygame.Surface,
    _clock:  pygame.time.Clock,
    _hands,
    _cam,
):
    """pygame/mediapipe/cv2 초기화 완료 후 공유 변수를 채운다."""
    global screen, clock, WIN_W, WIN_H
    global FONT_FILE
    global font_huge, font_big, font_mid, font_small, font_tiny, font_micro
    global hands, cam
    global _tip_img, _select_timer_imgs, _back_timer_imgs, _exit_timer_imgs

    screen = _screen
    clock  = _clock
    WIN_W, WIN_H = screen.get_size()

    hands = _hands
    cam   = _cam

    # 폰트
    FONT_FILE = _pick_font_path()
    font_huge  = _font(110)
    font_big   = _font(90)
    font_mid   = _font(66)
    font_small = _font(46)
    font_tiny  = _font(34)
    font_micro = _font(28)

    # 커서 이미지
    try:
        img = pygame.image.load("assets/ui/tip_cursor.png").convert_alpha()
        _tip_img = pygame.transform.smoothscale(img, (80, 80))
    except Exception:
        _tip_img = None

    # 타이머 이미지 (select / back / exit)
    for _i in [1, 2, 3]:
        for prefix, store in [
            ("select", _select_timer_imgs),
            ("back",   _back_timer_imgs),
            ("exit",   _exit_timer_imgs),
        ]:
            try:
                img = pygame.image.load(
                    f"assets/ui/{prefix}_{_i}.png"
                ).convert_alpha()
                store[_i] = pygame.transform.smoothscale(img, (300, 80))
            except Exception:
                store[_i] = None
