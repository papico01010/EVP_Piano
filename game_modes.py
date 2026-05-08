"""
game_modes.py - 게임 플로우 모듈
"""
import sys
import math
import time
import threading
import queue
import pygame

import shared
import audio
import gesture
import ui
import auth

# ── TTS 글로벌 워커 ─────────────────────────────────────────────────────
_tts_queue: queue.Queue = queue.Queue()
_tts_engine_ref = [None]
_tts_interrupted = [False]


def _make_tts_engine():
    import pyttsx3
    # 캐시된 손상 엔진을 피하기 위해 전역 캐시를 비우고 새로 초기화
    pyttsx3._activeEngines.clear()
    engine = pyttsx3.init()
    engine.setProperty("rate", 160)
    engine.setProperty("volume", 1.0)
    return engine


def _tts_worker():
    try:
        engine = _make_tts_engine()
        _tts_engine_ref[0] = engine
        while True:
            msg = _tts_queue.get()
            if msg is None:
                break
            # 큐에 더 최신 메시지가 있으면 건너뜀
            while not _tts_queue.empty():
                try:
                    msg = _tts_queue.get_nowait()
                except queue.Empty:
                    break
            _tts_interrupted[0] = False
            try:
                engine.say(msg)
                engine.runAndWait()
            except Exception:
                pass
            # 중단됐으면 엔진 재초기화 (endLoop 후 엔진 상태 복구)
            if _tts_interrupted[0]:
                try:
                    del engine
                except Exception:
                    pass
                engine = _make_tts_engine()
                _tts_engine_ref[0] = engine
    except Exception:
        pass


threading.Thread(target=_tts_worker, daemon=True).start()


def stop_tts():
    """큐를 비우고 현재 발화를 중단한다."""
    while not _tts_queue.empty():
        try:
            _tts_queue.get_nowait()
        except queue.Empty:
            break
    engine = _tts_engine_ref[0]
    if engine:
        _tts_interrupted[0] = True
        try:
            engine.endLoop()
        except Exception:
            pass


def speak(msg: str):
    """TTS 메시지를 큐에 넣어 재생"""
    _tts_queue.put(msg)

# ── 음악 유틸 ─────────────────────────────────────────────────────────
def _n7_to_12(n):
    return n[:-1]


def note_to_kor(note: str) -> str:
    if not note:
        return ""
    base = note[:-1] if note[-1].isdigit() else note
    num  = note[-1]  if note[-1].isdigit() else ""
    return f"{audio.NOTE_NAME_MAP.get(base, base)}{num}"


# ── 이미지 캐시 (모듈 로드 시 채워짐) ────────────────────────────────
_title_imgs: dict  = {}
_note_imgs: dict   = {}
_score_imgs: dict  = {}
_sheet_imgs: dict  = {}   # {song_name: {1: Surface, 2: Surface, ...}}
_play_bg_imgs: dict = {}  # {"follow_반짝반짝": Surface, "challenge_반짝반짝": Surface, ...}
_program_tip_img   = None  # program_tip.png (악보 위 네온 포인터)

# ── 악보 팁 좌표 (음표 인덱스별, 추후 악보마다 채워 넣을 예정) ────────────
# SONG_TIP_X: {song_name: [note_idx별 x좌표, ...]}
# SONG_TIP_Y: {song_name: y좌표}  (없으면 기본값 530)
_TIP_Y_DEFAULT = 530

SONG_TIP_Y: dict = {
    "반짝반짝":   530,
    "런던":       530,
    "생축":       530,
    "징글벨":     530,
    "나비야나비야": 530,
}

SONG_TIP_X: dict = {
    "반짝반짝": [
        113, 245, 390, 525, 668, 800, 945,  # 1문단
         90, 225, 372, 510, 655, 795, 940,  # 2문단
         90, 225, 375, 510, 655, 795, 940,  # 3문단
         90, 225, 375, 510, 655, 795, 940,  # 4문단
         90, 225, 375, 510, 655, 795, 940,  # 5문단
         90, 225, 375, 510, 655, 795, 935,  # 6문단
    ],
    "런던": [
        113, 210, 245, 310, 390, 455, 525, 670, 738, 800, 950, 1015, 1080,  # 1문단
         90, 190, 220, 290, 365, 435, 500, 650, 790, 940, 1000,              # 2문단
    ],
    "생축": [
        290, 350, 390, 480, 563, 630, 670, 850, 920, 950, 1040, 1120, 1190,  # 1문단
         90, 270, 335, 370, 460, 550, 650, 745, 1120, 1190,                  # 2문단
         90, 195, 300, 420,                                                   # 3문단
    ],
    "징글벨": [
        113, 180, 245, 390, 455, 520, 670, 740, 800, 870, 950,                          # 1문단
         90, 150, 220, 290, 370, 440, 510, 580, 660, 730, 790, 860, 940, 1080,          # 2문단
         90, 150, 220, 370, 440, 510, 660, 720, 790, 860, 945,                          # 3문단
         90, 150, 220, 290, 370, 440, 510, 580, 650, 720, 790, 860, 940,                # 4문단
    ],
    "나비야나비야": [
        113, 180, 245, 390, 460, 520, 670, 735, 800, 870, 950, 1020, 1080,  # 1문단
         90, 150, 220, 370, 435, 510, 660, 725, 795, 865, 945, 1015, 1080,  # 2문단
         90, 155, 220, 290, 370, 435, 510, 660, 725, 795, 860, 945, 1010, 1080,  # 3문단
         90, 150, 220, 370, 435, 510, 660, 725, 795, 865, 945, 1015, 1080,  # 4문단
    ],
    "세인츠": [
        180, 245, 310, 395, 737, 805, 870, 950,  # 1문단
        155, 220, 290, 372, 510, 660, 795, 945,  # 2문단
        225, 295, 372, 578, 660, 795, 945, 1016, # 3문단
        223, 292, 370, 506, 653, 785, 935,        # 4문단
    ],
    "비행기": [
        110, 217, 245, 315, 390, 457, 522, 670, 735, 805, 952, 1016, 1082,  # 1문단
         90, 192, 218, 285, 370, 435, 505, 650, 720, 790, 855, 935,          # 2문단
    ],
    "로우로우로우": [
        110, 245, 392, 480, 525, 670, 763, 800, 895, 950,                              # 1문단
         90, 133, 176, 220, 264, 315, 372, 411, 457, 502, 550, 596, 650, 743, 788, 882, 936,  # 2문단
    ],
    "환희": [
        110, 175, 245, 315, 392, 457, 522, 590, 670, 734, 806, 872, 952, 1016, 1082,                    # 1문단
         90, 155, 220, 285, 372, 435, 510, 580, 659, 723, 795, 863, 945, 1012, 1080,                    # 2문단
         90, 153, 220, 293, 372, 435, 471, 510, 580, 660, 723, 761, 792, 863, 945, 1016, 1080,          # 3문단
         90, 155, 220, 285, 372, 435, 510, 580, 659, 723, 795, 863, 945, 1012, 1080,                    # 4문단
    ],
    "양키": [
        131, 193, 264, 325, 407, 471, 536, 600, 680, 743, 808, 874, 952, 1087,  # 1문단
        105, 165, 240, 305, 385, 445, 515, 581, 663, 725, 790, 861, 937, 1069,  # 2문단
    ],
}

# 노래 영문 키 매핑 (파일명용)
_SONG_KEY_MAP = {
    "반짝반짝": "twinkle", "생축": "birthday", "징글벨": "jingle",
    "비행기": "airplane", "환희": "ode", "런던": "london",
    "나비야나비야": "butterfly", "세인츠": "saints", "로우로우로우": "rowrow", "양키": "yankee",
}

# 악보 섹션 정보: {song_name: 섹션당_음표수}  (섹션 수 = 전체음표 / 섹션당음표수)
SONG_SHEET_SECTIONS = {
    "반짝반짝": [7, 14, 21, 28, 35],  # 1~6문단 각 7음
    "징글벨": [11, 25, 36, 50],  # 4문단 경계 (누적 음표 수)
    "로우로우로우": [10],   # 1문단 10음, 2문단 17음
    "양키": [14],           # 1문단 14음, 2문단 14음
    "생축": [13, 23],      # 1문단 13음, 2문단 10음, 3문단 4음
    "나비야나비야": [13, 26, 40], # 1~2문단 각 13음, 3문단 14음, 4문단 13음
    "세인츠": [8, 16, 24], # 1~3문단 각 8음, 4문단 7음
    "비행기": [13],        # 1문단 13음, 2문단 12음
    "런던": [13],          # 1문단 13음, 2문단 11음
    "환희": [15, 30, 47], # 1~2문단 각 15음, 3문단 17음, 4문단 15음
}


def _get_sheet_section(song_name: str, idx: int):
    """현재 음표 인덱스(idx)가 속한 섹션 번호(1부터) 반환."""
    sec_info = SONG_SHEET_SECTIONS.get(song_name)
    if sec_info is None:
        return None
    if isinstance(sec_info, list):
        for i, boundary in enumerate(sec_info):
            if idx < boundary:
                return i + 1
        return len(sec_info) + 1
    return idx // sec_info + 1


def _load_image_cache():
    """SONGS 키를 참고해 관련 이미지를 미리 로드한다."""
    global _title_imgs, _note_imgs, _score_imgs, _sheet_imgs, _play_bg_imgs, _program_tip_img

    # 악보 팁 이미지
    try:
        _program_tip_img = pygame.image.load("assets/ui/program_tip.png").convert_alpha()
    except Exception:
        _program_tip_img = None

    # 타이틀 이미지
    _title_imgs = {}
    for _song in audio.SONGS.keys():
        for _mode in ["follow", "challenge"]:
            _key = f"{_mode}_{_song}"
            try:
                _img = pygame.image.load(
                    f"assets/ui/title_{_mode}_{_song}.png"
                ).convert_alpha()
                _title_imgs[_key] = pygame.transform.smoothscale(_img, (500, 80))
            except Exception:
                _title_imgs[_key] = None

    # 계이름 이미지
    _note_imgs = {}
    for _note in ["도4","레4","미4","파4","솔4","라4","시4",
                  "도#4","레#4","파#4","솔#4","라#4"]:
        try:
            _img = pygame.image.load(
                f"assets/ui/note_{_note}.png"
            ).convert_alpha()
            _note_imgs[_note] = pygame.transform.smoothscale(_img, (200, 80))
        except Exception:
            _note_imgs[_note] = None

    # 악보 이미지
    _score_imgs = {}
    for _song in audio.SONGS.keys():
        try:
            _img = pygame.image.load(
                f"assets/ui/score_{_song}.png"
            ).convert_alpha()
            new_w = int(shared.WIN_W * 0.6)
            new_h = int(229 * 0.6)
            _score_imgs[_song] = pygame.transform.smoothscale(_img, (new_w, new_h))
        except Exception:
            _score_imgs[_song] = None

    # 악보 섹션 이미지 (assets/ui/<key>_<n>.png)
    # twinkle 스타일(1280×720 풀캔버스)은 그대로 스케일,
    # 스트립 스타일(1180×113 등)은 너비만 WIN_W로 유지하고 twinkle 기준 y 위치에 배치
    _SHEET_Y_FRAC = 0.79   # twinkle 기준: 악보 상단이 WIN_H 의 약 79% 지점
    _sheet_imgs = {}
    for _song, _nps in SONG_SHEET_SECTIONS.items():
        _key = _SONG_KEY_MAP.get(_song, _song)
        _total = len(audio.SONGS.get(_song, []))
        _n_sections = len(_nps) + 1 if isinstance(_nps, list) else (_total // _nps)
        _sheet_imgs[_song] = {}
        for _i in range(1, _n_sections + 1):
            try:
                _img = pygame.image.load(
                    f"assets/ui/{_key}_{_i}.png"
                ).convert_alpha()
                _orig_w, _orig_h = _img.get_size()
                if _orig_h >= shared.WIN_H * 0.3:
                    # 풀캔버스 스타일 (twinkle 등): 화면 크기로 그대로 스케일
                    _sheet_imgs[_song][_i] = pygame.transform.smoothscale(
                        _img, (shared.WIN_W, shared.WIN_H)
                    )
                else:
                    # 스트립 스타일: twinkle(1280px 기준) 비율로 너비 스케일 후 중앙 배치
                    _new_w = int(_orig_w * shared.WIN_W / 1280)
                    _new_h = int(_orig_h * _new_w / _orig_w)
                    _strip = pygame.transform.smoothscale(_img, (_new_w, _new_h))
                    _canvas = pygame.Surface((shared.WIN_W, shared.WIN_H), pygame.SRCALPHA)
                    _canvas.fill((0, 0, 0, 0))
                    _x = (shared.WIN_W - _new_w) // 2
                    _y = int(shared.WIN_H * _SHEET_Y_FRAC)
                    _canvas.blit(_strip, (_x, _y))
                    _sheet_imgs[_song][_i] = _canvas
            except Exception:
                _sheet_imgs[_song][_i] = None

    # 연주 화면 곡 이미지 (assets/ui/play_{key}.png, 611×48)
    _play_bg_imgs = {}
    for _song in audio.SONGS.keys():
        _key = _SONG_KEY_MAP.get(_song, _song)
        try:
            _img = pygame.image.load(
                f"assets/ui/play_{_key}.png"
            ).convert_alpha()
            _play_bg_imgs[_song] = pygame.transform.smoothscale(_img, (611, 48))
        except Exception:
            _play_bg_imgs[_song] = None


# ── 음성인식 헬퍼 ─────────────────────────────────────────────────────
def start_voice_listener(result_holder):
    """백그라운드에서 음성 인식 → result_holder["cmd"]에 결과 저장"""
    import speech_recognition as sr
    try:
        import pyaudio  # noqa: F401
    except ImportError:
        result_holder["cmd"] = "no_audio"
        return threading.Thread(target=lambda: None, daemon=True)

    def _listen():
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                aud = recognizer.listen(source, timeout=5, phrase_time_limit=4)
            text = recognizer.recognize_google(aud, language="ko-KR")
            if "다시" in text:
                result_holder["cmd"] = "replay"
            elif "악보" in text or "선택" in text:
                result_holder["cmd"] = "select"
            else:
                result_holder["cmd"] = "retry"
        except sr.WaitTimeoutError:
            result_holder["cmd"] = "retry"
        except sr.UnknownValueError:
            result_holder["cmd"] = "retry"
        except Exception:
            result_holder["cmd"] = "retry"

    t = threading.Thread(target=_listen, daemon=True)
    t.start()
    return t


# ── 속도 선택 ─────────────────────────────────────────────────────────
def select_play_speed():
    """빠르게/중간/느리게 선택 → sleep 시간 반환"""
    options = [
        {"label": "느리게", "delay": 0.7},
        {"label": "중간",   "delay": 0.4},
        {"label": "빠르게", "delay": 0.25},
    ]
    selected     = None
    select_start = None
    hold_sec     = 1
    btn_w = int(shared.WIN_W * 0.2)
    btn_h = int(shared.WIN_H * 0.12)
    gap   = int(shared.WIN_W * 0.05)
    total_w = btn_w * 3 + gap * 2
    start_x = shared.WIN_W // 2 - total_w // 2
    btn_y   = int(shared.WIN_H * 0.5)

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)
        ui.draw_title_banner("연주 속도", top_pad=18)
        ui.draw_lines_center(["원하는 속도를 골라봐!"],
                             int(shared.WIN_H * 0.38), size="small", line_gap=8)

        tip = gesture.get_index_tip_xy(res)

        hovered = None
        for i, opt in enumerate(options):
            x  = start_x + i * (btn_w + gap)
            r  = pygame.Rect(x, btn_y, btn_w, btn_h)
            is_hov = tip and r.collidepoint(tip)
            col = (100, 180, 255) if is_hov else (60, 60, 60)
            pygame.draw.rect(shared.screen, col, r, border_radius=10)
            lbl = shared.font_small.render(opt["label"], True, (255, 255, 255))
            shared.screen.blit(
                lbl, (r.centerx - lbl.get_width() // 2,
                      r.centery - lbl.get_height() // 2)
            )
            if is_hov:
                hovered = opt

        if hovered:
            if selected != hovered:
                selected     = hovered
                select_start = time.time()
            else:
                el       = time.time() - select_start

                if el >= hold_sec:
                    return hovered["delay"]
        else:
            selected     = None
            select_start = None

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(hovered))
        if r == "BACK":
            return 0.4
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── yes / no 화면 ────────────────────────────────────────────────────
def yes_no_screen(message, hold_sec=1, bg_img=None):
    btn_w   = 500
    btn_h   = 100
    yes_box = pygame.Rect(int(shared.WIN_W * 0.08), int(shared.WIN_H * 0.38),
                          btn_w, btn_h)
    no_box  = pygame.Rect(int(shared.WIN_W * 0.57), int(shared.WIN_H * 0.38),
                          btn_w, btn_h)
    ys = ns = None

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)
        if bg_img:
            shared.screen.blit(bg_img, (0, 0))
        ui.draw_lines_center([message], 120, size="mid", line_gap=12)

        tip = gesture.get_index_tip_xy(res)
        for rect, key in [(yes_box, "yes"), (no_box, "no")]:
            img_set = shared.BTN_IMAGES.get(key)
            if img_set and img_set.get("normal") and img_set.get("active"):
                state    = "active" if (tip and rect.collidepoint(tip)) else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(base_img, (rect.width, rect.height))
                shared.screen.blit(scaled, rect.topleft)
            else:
                col = (0, 200, 0) if key == "yes" else (200, 0, 0)
                pygame.draw.rect(shared.screen, col, rect, 6)

        hover = bool(tip and (yes_box.collidepoint(tip) or no_box.collidepoint(tip)))

        if tip and yes_box.collidepoint(tip):
            if ys is None:
                ys = time.time()
            el       = time.time() - ys

            if el >= hold_sec:
                return True
        else:
            ys = None

        if tip and no_box.collidepoint(tip):
            if ns is None:
                ns = time.time()
            el       = time.time() - ns

            if el >= hold_sec:
                return False
        else:
            ns = None

        r = ui.update_back_and_exit_timers(res, inhibit_back=hover)
        if r == "EXIT":
            pygame.quit(); sys.exit()
        if r == "BACK":
            return "BACK"

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        pygame.display.flip()


# ── 확인 화면 ─────────────────────────────────────────────────────────
def confirm_mode(chosen):
    if chosen == "자유연주":
        img_key = "confirm_free"
        tts_msg = "자유연주에서는 자유롭게 피아노를 연주할 수 있어요. 자유연주를 플레이 하실 건가요?"
    elif chosen == "따라연주":
        img_key = "confirm_follow"
        tts_msg = "따라연주에서는 원하는 악보를 선택한 후 가이드 건반을 따라 피아노를 연주할 수 있어요. 따라연주를 플레이 하실 건가요?"
    else:
        img_key = "confirm_challenge"
        tts_msg = "도전연주에서는 원하는 악보를 선택한 후 가이드 건반 없이 악보를 보며 연주해야 해요. 올바른 연주를 통해 높은 등급에 도전해보세요. 도전연주를 플레이 하실 건가요?"

    stop_tts()
    speak(tts_msg)

    try:
        img = pygame.image.load(f"assets/ui/{img_key}.png").convert_alpha()
        img = pygame.transform.smoothscale(img, (shared.WIN_W, shared.WIN_H))
    except Exception as e:
        print(f"confirm 이미지 로드 실패: {e}")
        img = None

    ans = yes_no_screen("", hold_sec=1, bg_img=img)
    if ans is not True:
        stop_tts()
    return ans is True


# # ── 웰컴 화면 ─────────────────────────────────────────────────────────
# def welcome_screen():
#     try:
#         img = pygame.image.load("assets/ui/welcome.png").convert_alpha()
#         img = pygame.transform.smoothscale(img, (shared.WIN_W, shared.WIN_H))
#     except Exception:
#         img = None

#     st = time.time()
#     while time.time() - st < 5:
#         ui.handle_common_events()
#         rgb, _ = gesture.cam_frame_rgb()
#         if rgb is None:
#             continue
#         res = shared.hands.process(rgb)
#         ui.blit_camera_bg(rgb)

#         if img:
#             shared.screen.blit(img, (0, 0))
#         else:
#             ui.draw_lines_center(
#                 ["EVP에 온 걸 환영해용"],
#                 y_start=shared.WIN_H // 2 - 60,
#                 size="mid", line_gap=14,
#             )

#         tip = gesture.get_index_tip_xy(res)
#         if tip:
#             if shared._tip_img:
#                 shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
#             else:
#                 pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

#         r = ui.update_back_and_exit_timers(res, inhibit_back=True)
#         if r == "EXIT":
#             pygame.quit(); sys.exit()

#         pygame.display.flip()


# ── 모드 선택 ─────────────────────────────────────────────────────────
def mode_select():
    _btn_w, _btn_h, _btn_gap = 500, 100, 40
    _btn_x = (shared.WIN_W - _btn_w) // 2
    _btn_y0 = (shared.WIN_H - (3 * _btn_h + 2 * _btn_gap)) // 2 + 80
    boxes = [
        {"name": "자유연주",  "img_key": "mode_free",
         "rect": pygame.Rect(_btn_x, _btn_y0, _btn_w, _btn_h)},
        {"name": "따라연주",  "img_key": "mode_follow",
         "rect": pygame.Rect(_btn_x, _btn_y0 + _btn_h + _btn_gap, _btn_w, _btn_h)},
        {"name": "도전연주",  "img_key": "mode_challenge",
         "rect": pygame.Rect(_btn_x, _btn_y0 + 2 * (_btn_h + _btn_gap), _btn_w, _btn_h)},
    ]
    selected     = None
    select_start = None
    hold_sec     = 1
    try:
        bg = pygame.image.load("assets/ui/mode_select_bg.png").convert_alpha()
        bg = pygame.transform.smoothscale(bg, (shared.WIN_W, shared.WIN_H))
    except Exception:
        bg = None

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)
        if bg:
            shared.screen.blit(bg, (0, 0))

        tip = gesture.get_index_tip_xy(res)
        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        hover = None
        if tip:
            for b in boxes:
                if b["rect"].collidepoint(tip):
                    hover = b
                    break

        for b in boxes:
            img_set = shared.BTN_IMAGES.get(b["img_key"])
            if img_set and img_set.get("normal") and img_set.get("active"):
                state    = "active" if hover is b else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(
                    base_img, (b["rect"].width, b["rect"].height)
                )
                shared.screen.blit(scaled, b["rect"].topleft)
            else:
                pygame.draw.rect(shared.screen, (0, 0, 255), b["rect"], 6)

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        if hover:
            if selected is None:
                selected, select_start = hover, time.time()
            elif hover == selected:
                el       = time.time() - select_start

                if el >= hold_sec:
                    if confirm_mode(hover["name"]):
                        return hover["name"]
                    else:
                        selected     = None
                        select_start = None
            else:
                selected, select_start = hover, time.time()
        else:
            selected = None

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(hover))
        if r == "BACK":
            return "BACK_TO_DIFFICULTY"
        if r == "EXIT":
            pygame.quit(); sys.exit()

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        pygame.display.flip()


# ── 자유연주 루프 ─────────────────────────────────────────────────────
def free_play_loop():
    mnm        = audio.MultiNoteManager(decay_time=1.5)
    note_label = None
    start_time = time.time()
    COOLDOWN   = 3.0

    FINGER_NUM_LABEL = {
        "pinky": "5", "ring": "4", "middle": "3",
        "index": "2", "thumb": "1",
    }
    FINGER_PRESSED_COL = {
        "pinky":  (135, 206, 250),
        "ring":   (135, 206, 250),
        "middle": (135, 206, 250),
        "index":  (135, 206, 250),
        "thumb":  (135, 206, 250),
    }

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)

        pressed_notes = gesture.get_all_pressed_notes(res)
        if time.time() - start_time < COOLDOWN:
            pressed_notes = set()
        active_notes  = mnm.update(pressed_notes)
        gesture.is_index_press(res)

        note_label = " · ".join(
            note_to_kor(n) for n in sorted(active_notes)
        ) if active_notes else None

        ui.draw_and_debug(
            user_notes=pressed_notes,
            program_note=None,
            note_label_text=None,
        )

        if res and res.multi_hand_landmarks:
            for hand_idx, hand_lm in enumerate(res.multi_hand_landmarks):
                lm = hand_lm.landmark
                if res.multi_handedness and hand_idx < len(res.multi_handedness):
                    hand_label_str = (res.multi_handedness[hand_idx]
                                     .classification[0].label.lower())
                else:
                    hand_label_str = f"hand{hand_idx}"
                for fname, cfg in gesture.FINGER_CONFIG.items():
                    tip_i    = cfg["tip"]
                    tx       = int(lm[tip_i].x * shared.WIN_W)
                    ty       = int(lm[tip_i].y * shared.WIN_H)
                    hand_key = (hand_label_str, fname)
                    state    = gesture._finger_states.get(hand_key)
                    vel      = 0.0
                    if state and state.get("y_history"):
                        vel = state.get("velocity", 0.0)
                    num_str = FINGER_NUM_LABEL[fname]
                    col     = FINGER_PRESSED_COL[fname] \
                        if vel >= gesture.PRESS_VEL_TH else (255, 255, 255)
                    lbl    = shared.font_small_bold.render(num_str, True, col)
                    shadow = shared.font_small_bold.render(num_str, True, (0, 0, 0))
                    cx = tx - lbl.get_width()  // 2
                    cy = ty - lbl.get_height() // 2
                    shared.screen.blit(shadow, (cx + 2, cy + 2))
                    shared.screen.blit(lbl,    (cx,     cy))

        r = ui.update_back_and_exit_timers(res, inhibit_back=False)
        if r == "BACK":
            mnm.reset(); return
        if r == "EXIT":
            mnm.reset(); pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 따라연주 악보 선택 ────────────────────────────────────────────────
def score_practice_select():
    song_names = list(audio.SONGS.keys())

    try:
        song_bg = pygame.image.load("assets/ui/song_select_bg.png").convert_alpha()
        song_bg = pygame.transform.smoothscale(song_bg, (shared.WIN_W, shared.WIN_H))
    except Exception:
        song_bg = None

    SONG_KEYS = {
        "반짝반짝": "twinkle", "생축": "birthday", "징글벨": "jingle",
        "비행기": "airplane", "환희": "ode", "런던": "london",
        "나비야나비야": "butterfly", "세인츠": "saints", "로우로우로우": "rowrow", "양키": "yankee",
    }
    try:
        _start_n = pygame.image.load("assets/ui/song_start_normal.png").convert_alpha()
        _start_n = pygame.transform.smoothscale(_start_n, (260, 58))
    except Exception:
        _start_n = None
    try:
        _start_h = pygame.image.load("assets/ui/song_start_hover.png").convert_alpha()
        _start_h = pygame.transform.smoothscale(_start_h, (260, 58))
    except Exception:
        _start_h = None
    _speed_imgs = {}
    for _sk in ["slow", "mid", "fast"]:
        try:
            _sn = pygame.image.load(f"assets/ui/speed_{_sk}_normal.png").convert_alpha()
            _sn = pygame.transform.smoothscale(_sn, (72, 33))
        except Exception:
            _sn = None
        try:
            _sh = pygame.image.load(f"assets/ui/speed_{_sk}_hover.png").convert_alpha()
            _sh = pygame.transform.smoothscale(_sh, (72, 33))
        except Exception:
            _sh = None
        _speed_imgs[_sk] = {"normal": _sn, "hover": _sh}
    try:
        _speed_bg = pygame.image.load("assets/ui/speed_select_bg.png").convert_alpha()
    except Exception:
        _speed_bg = None
    song_imgs = {}
    for _name in song_names:
        _key = SONG_KEYS.get(_name, _name)
        try:
            _n = pygame.image.load(f"assets/ui/song_{_key}_normal.png").convert_alpha()
        except Exception:
            _n = None
        try:
            _h = pygame.image.load(f"assets/ui/song_{_key}_hover.png").convert_alpha()
        except Exception:
            _h = None
        try:
            _p = pygame.image.load(f"assets/ui/song_{_key}_preview.png").convert_alpha()
            _p = pygame.transform.smoothscale(_p, (260, 376)) # _preview.png 위치
        except Exception:
            _p = None
        song_imgs[_name] = {"normal": _n, "hover": _h, "preview": _p}

    selected        = None
    select_start    = None
    hold_sec        = 1
    btn_hover       = None
    btn_hover_start = None
    preview_song    = None
    selected_speed  = "mid"
    BTN_HOLD_SEC    = 1
    SPEED_DELAYS    = {"slow": 0.7, "mid": 0.4, "fast": 0.25}
    SPEED_POSITIONS = [("slow", 921, 576), ("mid", 1000, 576), ("fast", 1078, 576)] 
    # speed 버튼 세 개 x 871 950 1028 / y 576
    # 1차수정 : x + 20
    # 2차 : x + 40

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)

        if song_bg:
            shared.screen.blit(song_bg, (0, 0))

        tip = gesture.get_index_tip_xy(res)

        # 악보 버튼 툴
        PANEL_X, PANEL_Y = 130, 140
        PANEL_W, PANEL_H = 734, 545
        BTN_W,   BTN_H   = 352, 97
        gap              = 10

        raw_hovered = None
        for i, name in enumerate(song_names):
            col = i // 5
            row = i % 5
            x   = PANEL_X + col * (BTN_W + gap)
            y   = PANEL_Y + gap + row * (BTN_H + gap)
            r   = pygame.Rect(x, y, BTN_W, BTN_H)
            img_set    = song_imgs.get(name)
            is_hov     = bool(tip and r.collidepoint(tip))
            is_preview = (name == preview_song)
            if img_set and img_set.get("normal"):
                state    = "hover" if is_preview and img_set.get("hover") else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(base_img, (BTN_W, BTN_H))
                shared.screen.blit(scaled, r.topleft)
            else:
                c = (100, 180, 255) if is_preview else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, r, border_radius=8)
                lbl = shared.font_micro.render(name, True, (255, 255, 255))
                shared.screen.blit(
                    lbl, (r.centerx - lbl.get_width()  // 2,
                        r.centery - lbl.get_height() // 2)
                )
            if is_hov:
                raw_hovered = name

        # 1초 hover → preview 활성화 (손가락이 버튼 밖에 있으면 타이머 초기화)
        if raw_hovered:
            if raw_hovered != btn_hover:
                btn_hover       = raw_hovered
                btn_hover_start = time.time()
        else:
            btn_hover       = None
            btn_hover_start = None
        if btn_hover and btn_hover_start and (time.time() - btn_hover_start >= BTN_HOLD_SEC):
            if preview_song != btn_hover:
                preview_song = btn_hover
                selected     = None
                select_start = None

        if preview_song:
            _prev = song_imgs.get(preview_song, {}).get("preview")
            if _prev:
                shared.screen.blit(_prev, (906, 147))

            # 속도 선택 배경 + 버튼
            if _speed_bg:
                _speed_bg_scaled = pygame.transform.smoothscale(_speed_bg, (260, 86))
                shared.screen.blit(_speed_bg_scaled, (906, 537))
            for _sk, _sx, _sy in SPEED_POSITIONS:
                _sr = pygame.Rect(_sx, _sy, 72, 33)
                _is_shov = bool(tip and _sr.collidepoint(tip))
                _is_ssel = (selected_speed == _sk)
                _simg = _speed_imgs[_sk].get("hover" if (_is_shov or _is_ssel) else "normal")
                if _simg:
                    shared.screen.blit(_simg, _sr.topleft)
                else:
                    _sc = (100, 180, 255) if (_is_shov or _is_ssel) else (60, 60, 60)
                    pygame.draw.rect(shared.screen, _sc, _sr, border_radius=4)
                if _is_shov:
                    selected_speed = _sk

            start_rect = pygame.Rect(906, 634, 260, 58)
            is_start_hov = bool(tip and start_rect.collidepoint(tip))
            start_img = _start_h if is_start_hov and _start_h else _start_n
            if start_img:
                shared.screen.blit(start_img, start_rect.topleft)
            else:
                c = (100, 180, 255) if is_start_hov else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, start_rect, border_radius=8)

            if is_start_hov:
                if selected != preview_song:
                    selected     = preview_song
                    select_start = time.time()
                else:
                    el = time.time() - select_start
                    if el >= hold_sec:
                        song_practice_flow(selected, SPEED_DELAYS[selected_speed])
                        selected     = None
                        select_start = None
            else:
                selected     = None
                select_start = None

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(raw_hovered))
        if r == "BACK":
            return
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 따라연주 플로우 ───────────────────────────────────────────────────
def song_practice_flow(song_name, play_delay=0.4):
    melody      = audio.SONGS[song_name]
    _dur_list   = audio.SONG_DURATIONS.get(song_name, [])
    _pre_delays = audio.SONG_PRE_DELAYS.get(song_name, [])
    _speed_mult = play_delay / 0.4  # 0.4=보통 기준, slow→1.75x, fast→0.625x
    res         = None

    for _preview_idx, n in enumerate(melody):
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is not None:
            res = shared.hands.process(rgb)
            ui.blit_camera_bg(rgb)
            prog_note_overlay = n

            ui.draw_and_debug(
                user_note=None,
                program_note=prog_note_overlay,
                note_label_text=None,
            )
            _pb_img = _play_bg_imgs.get(song_name)
            if _pb_img:
                shared.screen.blit(_pb_img, (335, 69))
            _sec = _get_sheet_section(song_name, _preview_idx)
            if _sec:
                _sh_img = _sheet_imgs.get(song_name, {}).get(_sec)
                if _sh_img:
                    shared.screen.blit(_sh_img, (0, 0))
            _tip_xs = SONG_TIP_X.get(song_name)
            if _tip_xs and _preview_idx < len(_tip_xs) and _program_tip_img:
                _tip_y = SONG_TIP_Y.get(song_name, _TIP_Y_DEFAULT)
                shared.screen.blit(_program_tip_img, (_tip_xs[_preview_idx], _tip_y))
            r = ui.update_back_and_exit_timers(res, inhibit_back=False)
            if r == "BACK":
                return "back_to_practice_menu"
            if r == "EXIT":
                pygame.quit(); sys.exit()
            pygame.display.flip()
        _pre = (_pre_delays[_preview_idx] if _preview_idx < len(_pre_delays) else 0) * _speed_mult
        if _pre > 0:
            time.sleep(_pre)
        _dur = audio.NOTE_DUR.get(
            _dur_list[_preview_idx] if _preview_idx < len(_dur_list) else "Q", 0.5) * _speed_mult
        audio.get_sound(n[:-1], int(n[-1])).play().fadeout(int(_dur * 700))
        time.sleep(_dur)

    tip = gesture.get_index_tip_xy(res) if res else None
    if tip:
        if shared._tip_img:
            shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
        else:
            pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

    nh  = audio.NoteHoldManager(decay_time=1.5)
    idx = 0

    FINGER_NUM_LABEL = {
        "pinky": "5", "ring": "4", "middle": "3",
        "index": "2", "thumb": "1",
    }
    FINGER_PRESSED_COL = {
        "pinky":  (135, 206, 250),
        "ring":   (135, 206, 250),
        "middle": (135, 206, 250),
        "index":  (135, 206, 250),
        "thumb":  (135, 206, 250),
    }

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)

        pressed_notes = gesture.get_all_pressed_notes(res)
        gesture.is_index_press(res)

        prev_state  = nh.state
        target_note = melody[idx]
        target12    = target_note[:-1]
        target_oct  = int(target_note[-1])
        if target_note in pressed_notes:
            nh.update(True, target12, target_oct)
            note_label = note_to_kor(target_note)
        else:
            nh.update(False, None, None)

        ui.blit_camera_bg(rgb)

        prog_overlay = melody[idx] if idx < len(melody) else None
        ui.draw_and_debug(
            user_notes=pressed_notes,
            program_note=prog_overlay,
            note_label_text=None,
        )
        _pb_img = _play_bg_imgs.get(song_name)
        if _pb_img:
            shared.screen.blit(_pb_img, (335, 69))
        _sc = _score_imgs.get(song_name)
        if _sc:
            shared.screen.blit(
                _sc, (shared.WIN_W // 2 - int(shared.WIN_W * 0.3),
                      shared.WIN_H - int(229 * 0.8))
            )

        _sec = _get_sheet_section(song_name, idx)
        if _sec:
            _sh_img = _sheet_imgs.get(song_name, {}).get(_sec)
            if _sh_img:
                shared.screen.blit(_sh_img, (0, 0))
        _tip_xs = SONG_TIP_X.get(song_name)
        if _tip_xs and idx < len(_tip_xs) and _program_tip_img:
            _tip_y = SONG_TIP_Y.get(song_name, _TIP_Y_DEFAULT)
            shared.screen.blit(_program_tip_img, (_tip_xs[idx], _tip_y))

        if res and res.multi_hand_landmarks:
            for hand_idx, hand_lm in enumerate(res.multi_hand_landmarks):
                lm = hand_lm.landmark
                if res.multi_handedness and hand_idx < len(res.multi_handedness):
                    hand_label_str = (res.multi_handedness[hand_idx]
                                     .classification[0].label.lower())
                else:
                    hand_label_str = f"hand{hand_idx}"
                for fname, cfg in gesture.FINGER_CONFIG.items():
                    tip_i    = cfg["tip"]
                    tx       = int(lm[tip_i].x * shared.WIN_W)
                    ty       = int(lm[tip_i].y * shared.WIN_H)
                    hand_key = (hand_label_str, fname)
                    state    = gesture._finger_states.get(hand_key)
                    vel      = 0.0
                    if state and state.get("y_history"):
                        vel = state.get("velocity", 0.0)
                    num_str = FINGER_NUM_LABEL[fname]
                    col     = FINGER_PRESSED_COL[fname] \
                        if vel >= gesture.PRESS_VEL_TH else (255, 255, 255)
                    lbl    = shared.font_small_bold.render(num_str, True, col)
                    shadow = shared.font_small_bold.render(num_str, True, (0, 0, 0))
                    cx = tx - lbl.get_width()  // 2
                    cy = ty - lbl.get_height() // 2
                    shared.screen.blit(shadow, (cx + 2, cy + 2))
                    shared.screen.blit(lbl,    (cx,     cy))

        r = ui.update_back_and_exit_timers(res, inhibit_back=False)
        if r == "BACK":
            nh.reset(); return "back_to_practice_menu"
        if r == "EXIT":
            nh.reset(); pygame.quit(); sys.exit()

        if prev_state == "idle" and nh.state == "pressed":
            idx += 1
            if idx >= len(melody):
                nh.reset()
                try:
                    practice_result_bg = pygame.image.load(
                        "assets/ui/practice_result_bg.png"
                    ).convert_alpha()
                    practice_result_bg = pygame.transform.smoothscale(
                        practice_result_bg, (shared.WIN_W, shared.WIN_H)
                    )
                except Exception:
                    practice_result_bg = None
                try:
                    finish_title_img = pygame.image.load(
                        "assets/ui/finish_title.png"
                    ).convert_alpha()
                    finish_title_img = pygame.transform.smoothscale(
                        finish_title_img,
                        (int(shared.WIN_W * 0.4), int(shared.WIN_H * 0.3))
                    )
                except Exception:
                    finish_title_img = None
                try:
                    finish_guide_img = pygame.image.load(
                        "assets/ui/finish_guide.png"
                    ).convert_alpha()
                    finish_guide_img = pygame.transform.smoothscale(
                        finish_guide_img,
                        (int(shared.WIN_W * 0.5), int(shared.WIN_H * 0.4))
                    )
                except Exception:
                    finish_guide_img = None

                voice_result = {"cmd": None}
                voice_thread = start_voice_listener(voice_result)
                _voice_retry_time = 0
                while True:
                    ui.handle_common_events()
                    rgb, _ = gesture.cam_frame_rgb()
                    if rgb is None:
                        continue
                    res = shared.hands.process(rgb)
                    ui.blit_camera_bg(rgb)
                    if practice_result_bg:
                        shared.screen.blit(practice_result_bg, (0, 0))
                    tip = gesture.get_index_tip_xy(res)
                    if tip:
                        if shared._tip_img:
                            shared.screen.blit(shared._tip_img,
                                               (tip[0] - 40, tip[1] - 40))
                        else:
                            pygame.draw.circle(shared.screen,
                                               (255, 255, 0), tip, 12, 0)
                    r2 = ui.update_back_and_exit_timers(res, inhibit_back=False)
                    if r2 == "BACK":
                        return "back_to_practice_menu"
                    if r2 == "EXIT":
                        pygame.quit(); sys.exit()
                    if voice_result["cmd"] == "replay":
                        song_practice_flow(song_name)
                        return
                    elif voice_result["cmd"] == "select":
                        return
                    if not voice_thread.is_alive() and voice_result["cmd"] not in ("replay", "select"):
                        now = time.time()
                        if now - _voice_retry_time >= 0.5:
                            voice_result["cmd"] = None
                            voice_thread = start_voice_listener(voice_result)
                            _voice_retry_time = now
                    pygame.display.flip()

        pygame.display.flip()


# ── 도전연주 악보 선택 ────────────────────────────────────────────────
def challenge_practice_select():
    song_names = list(audio.SONGS.keys())

    try:
        song_bg = pygame.image.load("assets/ui/song_select_bg.png").convert_alpha()
        song_bg = pygame.transform.smoothscale(song_bg, (shared.WIN_W, shared.WIN_H))
    except Exception:
        song_bg = None

    SONG_KEYS = {
        "반짝반짝": "twinkle", "생축": "birthday", "징글벨": "jingle",
        "비행기": "airplane", "환희": "ode", "런던": "london",
        "나비야나비야": "butterfly", "세인츠": "saints", "로우로우로우": "rowrow", "양키": "yankee",
    }
    try:
        _start_n = pygame.image.load("assets/ui/song_start_normal.png").convert_alpha()
        _start_n = pygame.transform.smoothscale(_start_n, (260, 58))
    except Exception:
        _start_n = None
    try:
        _start_h = pygame.image.load("assets/ui/song_start_hover.png").convert_alpha()
        _start_h = pygame.transform.smoothscale(_start_h, (260, 58))
    except Exception:
        _start_h = None
    _speed_imgs = {}
    for _sk in ["slow", "mid", "fast"]:
        try:
            _sn = pygame.image.load(f"assets/ui/speed_{_sk}_normal.png").convert_alpha()
            _sn = pygame.transform.smoothscale(_sn, (72, 33))
        except Exception:
            _sn = None
        try:
            _sh = pygame.image.load(f"assets/ui/speed_{_sk}_hover.png").convert_alpha()
            _sh = pygame.transform.smoothscale(_sh, (72, 33))
        except Exception:
            _sh = None
        _speed_imgs[_sk] = {"normal": _sn, "hover": _sh}
    try:
        _speed_bg = pygame.image.load("assets/ui/speed_select_bg.png").convert_alpha()
    except Exception:
        _speed_bg = None
    song_imgs = {}
    for _name in song_names:
        _key = SONG_KEYS.get(_name, _name)
        try:
            _n = pygame.image.load(f"assets/ui/song_{_key}_normal.png").convert_alpha()
        except Exception:
            _n = None
        try:
            _h = pygame.image.load(f"assets/ui/song_{_key}_hover.png").convert_alpha()
        except Exception:
            _h = None
        try:
            _p = pygame.image.load(f"assets/ui/song_{_key}_preview.png").convert_alpha()
            _p = pygame.transform.smoothscale(_p, (260, 376))
        except Exception:
            _p = None
        song_imgs[_name] = {"normal": _n, "hover": _h, "preview": _p}

    selected        = None
    select_start    = None
    hold_sec        = 1
    btn_hover       = None
    btn_hover_start = None
    preview_song    = None
    selected_speed  = "mid"
    BTN_HOLD_SEC    = 1
    SPEED_DELAYS    = {"slow": 0.7, "mid": 0.4, "fast": 0.25}
    SPEED_POSITIONS = [("slow", 921, 576), ("mid", 1000, 576), ("fast", 1078, 576)] 

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)

        if song_bg:
            shared.screen.blit(song_bg, (0, 0))

        tip = gesture.get_index_tip_xy(res)

        PANEL_X, PANEL_Y = 130, 140
        PANEL_W, PANEL_H = 734, 545
        BTN_W,   BTN_H   = 352, 97
        gap              = 10

        raw_hovered = None
        for i, name in enumerate(song_names):
            col = i // 5
            row = i % 5
            x   = PANEL_X + col * (BTN_W + gap)
            y   = PANEL_Y + gap + row * (BTN_H + gap)
            r   = pygame.Rect(x, y, BTN_W, BTN_H)
            img_set    = song_imgs.get(name)
            is_hov     = bool(tip and r.collidepoint(tip))
            is_preview = (name == preview_song)
            if img_set and img_set.get("normal"):
                state    = "hover" if is_preview and img_set.get("hover") else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(base_img, (BTN_W, BTN_H))
                shared.screen.blit(scaled, r.topleft)
            else:
                c = (100, 180, 255) if is_preview else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, r, border_radius=8)
                lbl = shared.font_micro.render(name, True, (255, 255, 255))
                shared.screen.blit(
                    lbl, (r.centerx - lbl.get_width()  // 2,
                          r.centery - lbl.get_height() // 2)
                )
            if is_hov:
                raw_hovered = name

        # 1초 hover → preview 활성화 (손가락이 버튼 밖에 있으면 타이머 초기화)
        if raw_hovered:
            if raw_hovered != btn_hover:
                btn_hover       = raw_hovered
                btn_hover_start = time.time()
        else:
            btn_hover       = None
            btn_hover_start = None
        if btn_hover and btn_hover_start and (time.time() - btn_hover_start >= BTN_HOLD_SEC):
            if preview_song != btn_hover:
                preview_song = btn_hover
                selected     = None
                select_start = None

        if preview_song:
            _prev = song_imgs.get(preview_song, {}).get("preview")
            if _prev:
                shared.screen.blit(_prev, (906, 147))

            # 최고 등급 표시
            if shared.current_user:
                _rec = auth.get_records(shared.current_user).get(preview_song)
                if _rec:
                    _grade_str = f"최고 등급: {_rec['grade']}  ({_rec['score']}%)"
                    _GRADE_COLORS = {
                        "PERFECT": (255, 215, 0), "GREAT": (100, 220, 100),
                        "GOOD": (100, 180, 255), "BAD": (255, 140, 0), "TRY AGAIN": (255, 80, 80),
                    }
                    _gcol = _GRADE_COLORS.get(_rec["grade"], (255, 255, 255))
                    _gs = shared.font_micro_bold.render(_grade_str, True, _gcol)
                    shared.screen.blit(_gs, (906 + 130 - _gs.get_width() // 2, 200)) # 최고등급 x y 위치

            # 속도 선택 배경 + 버튼
            if _speed_bg:
                _speed_bg_scaled = pygame.transform.smoothscale(_speed_bg, (260, 86))
                shared.screen.blit(_speed_bg_scaled, (906, 537)) #_speed_bg_scaled x y 위치 설정, y 537이 맞음
            for _sk, _sx, _sy in SPEED_POSITIONS:
                _sr = pygame.Rect(_sx, _sy, 72, 33)
                _is_shov = bool(tip and _sr.collidepoint(tip))
                _is_ssel = (selected_speed == _sk)
                _simg = _speed_imgs[_sk].get("hover" if (_is_shov or _is_ssel) else "normal")
                if _simg:
                    shared.screen.blit(_simg, _sr.topleft)
                else:
                    _sc = (100, 180, 255) if (_is_shov or _is_ssel) else (60, 60, 60)
                    pygame.draw.rect(shared.screen, _sc, _sr, border_radius=4)
                if _is_shov:
                    selected_speed = _sk

            start_rect = pygame.Rect(906, 634, 260, 58)
            is_start_hov = bool(tip and start_rect.collidepoint(tip))
            start_img = _start_h if is_start_hov and _start_h else _start_n
            if start_img:
                shared.screen.blit(start_img, start_rect.topleft)
            else:
                c = (100, 180, 255) if is_start_hov else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, start_rect, border_radius=8)

            if is_start_hov:
                if selected != preview_song:
                    selected     = preview_song
                    select_start = time.time()
                else:
                    el = time.time() - select_start
                    if el >= hold_sec:
                        challenge_practice_flow(selected, SPEED_DELAYS[selected_speed])
                        selected     = None
                        select_start = None
            else:
                selected     = None
                select_start = None

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(raw_hovered))
        if r == "BACK":
            return
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 도전연주 플로우 ───────────────────────────────────────────────────
def challenge_practice_flow(song_name, play_delay=0.4):
    melody      = audio.SONGS[song_name]
    _dur_list   = audio.SONG_DURATIONS.get(song_name, [])
    _pre_delays = audio.SONG_PRE_DELAYS.get(song_name, [])
    _speed_mult = play_delay / 0.4  # 0.4=보통 기준, slow→1.75x, fast→0.625x

    for _preview_idx, n in enumerate(melody):
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is not None:
            res = shared.hands.process(rgb)
            ui.blit_camera_bg(rgb)
            ui.draw_and_debug(
                user_note=None,
                program_note=n,
                note_label_text=None,
            )
            _pb_img = _play_bg_imgs.get(song_name)
            if _pb_img:
                shared.screen.blit(_pb_img, (335, 69))
            _sec = _get_sheet_section(song_name, _preview_idx)
            if _sec:
                _sh_img = _sheet_imgs.get(song_name, {}).get(_sec)
                if _sh_img:
                    shared.screen.blit(_sh_img, (0, 0))
            _tip_xs = SONG_TIP_X.get(song_name)
            if _tip_xs and _preview_idx < len(_tip_xs) and _program_tip_img:
                _tip_y = SONG_TIP_Y.get(song_name, _TIP_Y_DEFAULT)
                shared.screen.blit(_program_tip_img, (_tip_xs[_preview_idx], _tip_y))
            r = ui.update_back_and_exit_timers(res, inhibit_back=False)
            if r == "BACK":
                return
            if r == "EXIT":
                pygame.quit(); sys.exit()
            pygame.display.flip()
        _pre = (_pre_delays[_preview_idx] if _preview_idx < len(_pre_delays) else 0) * _speed_mult
        if _pre > 0:
            time.sleep(_pre)
        _dur = audio.NOTE_DUR.get(
            _dur_list[_preview_idx] if _preview_idx < len(_dur_list) else "Q", 0.5) * _speed_mult
        audio.get_sound(n[:-1], int(n[-1])).play().fadeout(int(_dur * 700))
        time.sleep(_dur)

    # 준비 카운트다운 3초
    try:
        _ready_bg = pygame.image.load("assets/ui/challenge_ready_bg.png").convert_alpha()
        _ready_bg = pygame.transform.smoothscale(_ready_bg, (shared.WIN_W, shared.WIN_H))
    except Exception:
        _ready_bg = None

    countdown_start = time.time()
    while True:
        remain = 3 - (time.time() - countdown_start)
        count_num = int(math.ceil(remain))
        if count_num <= 0:
            break
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)
        if _ready_bg:
            shared.screen.blit(_ready_bg, (0, 0))
        ui.draw_lines_center(
            [str(count_num)],
            shared.WIN_H // 2 - 40, size="huge", line_gap=0,
        )
        pygame.display.flip()

    idx                  = 0
    correct              = 0
    total                = 0
    note_label           = None
    last_pressed         = False
    wrong_notes          = set()
    wrong_display_until  = 0.0

    FINGER_NUM_LABEL = {
        "pinky": "5", "ring": "4", "middle": "3",
        "index": "2", "thumb": "1",
    }
    FINGER_PRESSED_COL = {
        "pinky":  (135, 206, 250),
        "ring":   (135, 206, 250),
        "middle": (135, 206, 250),
        "index":  (135, 206, 250),
        "thumb":  (135, 206, 250),
    }

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)

        pressed_notes = gesture.get_all_pressed_notes(res)
        gesture.is_index_press(res)

        target_note = melody[idx]
        target12    = target_note[:-1]

        currently_pressed = len(pressed_notes) > 0
        now = time.time()

        if now < wrong_display_until:
            currently_pressed = False

        if currently_pressed and not last_pressed:
            total += 1
            for note in pressed_notes:
                try:
                    n12  = note[:-1]
                    oct_ = int(note[-1])
                    audio.get_sound(n12, oct_).play().fadeout(350)
                except Exception:
                    pass
            if target_note in pressed_notes:
                correct    += 1
                note_label  = note_to_kor(target_note)
                wrong_notes = set()
            else:
                wrong_notes          = pressed_notes.copy()
                wrong_display_until  = now + 2.0
            idx += 1
        last_pressed = currently_pressed if now >= wrong_display_until else True

        # 모든 음 완료 → 결과 화면
        if idx >= len(melody):
            final_score = int((correct / total) * 100) if total > 0 else 0

            if final_score == 100:
                grade     = "PERFECT"
                grade_col = (255, 215, 0)
            elif final_score >= 75:
                grade     = "GREAT"
                grade_col = (100, 220, 100)
            elif final_score >= 50:
                grade     = "GOOD"
                grade_col = (100, 180, 255)
            elif final_score >= 25:
                grade     = "BAD"
                grade_col = (255, 140, 0)
            else:
                grade     = "TRY AGAIN"
                grade_col = (255, 80, 80)

            if shared.current_user:
                auth.save_record(shared.current_user, song_name, grade, final_score)

            result_start = time.time()
            while time.time() - result_start < 5:
                ui.handle_common_events()
                rgb, _ = gesture.cam_frame_rgb()
                if rgb is None:
                    continue
                res = shared.hands.process(rgb)
                ui.blit_camera_bg(rgb)
                grade_surf = shared.font_mid.render(grade, True, grade_col)
                shared.screen.blit(
                    grade_surf,
                    (shared.WIN_W // 2 - grade_surf.get_width() // 2,
                     shared.WIN_H // 2 - 100)
                )
                ui.draw_lines_center([
                    f"정확도: {final_score}%",
                    f"정답: {correct}개 / 전체: {total}개",
                ], shared.WIN_H // 2, size="small", line_gap=14)
                pygame.display.flip()

            try:
                practice_result_bg = pygame.image.load(
                    "assets/ui/practice_result_bg.png"
                ).convert_alpha()
                practice_result_bg = pygame.transform.smoothscale(
                    practice_result_bg, (shared.WIN_W, shared.WIN_H)
                )
            except Exception:
                practice_result_bg = None

            voice_result = {"cmd": None}
            voice_thread = start_voice_listener(voice_result)
            _voice_retry_time = 0
            while True:
                ui.handle_common_events()
                rgb, _ = gesture.cam_frame_rgb()
                if rgb is None:
                    continue
                res = shared.hands.process(rgb)
                ui.blit_camera_bg(rgb)
                if practice_result_bg:
                    shared.screen.blit(practice_result_bg, (0, 0))
                tip = gesture.get_index_tip_xy(res)
                if tip:
                    if shared._tip_img:
                        shared.screen.blit(shared._tip_img,
                                           (tip[0] - 40, tip[1] - 40))
                    else:
                        pygame.draw.circle(shared.screen,
                                           (255, 255, 0), tip, 12, 0)
                r2 = ui.update_back_and_exit_timers(res, inhibit_back=False)
                if r2 == "BACK":
                    return
                if r2 == "EXIT":
                    pygame.quit(); sys.exit()
                if voice_result["cmd"] == "replay":
                    challenge_practice_flow(song_name)
                    return
                elif voice_result["cmd"] == "select":
                    return
                if not voice_thread.is_alive() and voice_result["cmd"] not in ("replay", "select"):
                    now = time.time()
                    if now - _voice_retry_time >= 0.5:
                        voice_result["cmd"] = None
                        voice_thread = start_voice_listener(voice_result)
                        _voice_retry_time = now
                pygame.display.flip()

        ui.blit_camera_bg(rgb)

        ui.draw_and_debug(
            user_notes=pressed_notes,
            program_note=None,
            note_label_text=None,
        )
        _pb_img = _play_bg_imgs.get(song_name)
        if _pb_img:
            shared.screen.blit(_pb_img, (335, 69))
        _sc = _score_imgs.get(song_name)
        if _sc:
            shared.screen.blit(
                _sc, (shared.WIN_W // 2 - int(shared.WIN_W * 0.3),
                      shared.WIN_H - int(229 * 0.8))
            )

        _sec = _get_sheet_section(song_name, idx)
        if _sec:
            _sh_img = _sheet_imgs.get(song_name, {}).get(_sec)
            if _sh_img:
                shared.screen.blit(_sh_img, (0, 0))
        _tip_xs = SONG_TIP_X.get(song_name)
        if _tip_xs and idx < len(_tip_xs) and _program_tip_img:
            _tip_y = SONG_TIP_Y.get(song_name, _TIP_Y_DEFAULT)
            shared.screen.blit(_program_tip_img, (_tip_xs[idx], _tip_y))

        if time.time() < wrong_display_until and wrong_notes:
            _dark_overlay = pygame.Surface((shared.WIN_W, shared.WIN_H), pygame.SRCALPHA)
            _dark_overlay.fill((0, 0, 0, 100))
            shared.screen.blit(_dark_overlay, (0, 0))
            for note in wrong_notes:
                _err_img = ui._error_push_imgs.get(note)
                if _err_img:
                    shared.screen.blit(_err_img, (0, 0))
        else:
            wrong_notes = set()

        score_text = (
            f"정확도: {int((correct/total)*100) if total > 0 else 0}%"
            f"  ({correct}/{total})"
        )
        ui.draw_lines_center(
            [score_text, f"남은 음: {len(melody)-idx}개"],
            116, size="small", line_gap=8,
        )

        if res and res.multi_hand_landmarks:
            for hand_idx, hand_lm in enumerate(res.multi_hand_landmarks):
                lm = hand_lm.landmark
                if res.multi_handedness and hand_idx < len(res.multi_handedness):
                    hand_label_str = (res.multi_handedness[hand_idx]
                                     .classification[0].label.lower())
                else:
                    hand_label_str = f"hand{hand_idx}"
                for fname, cfg in gesture.FINGER_CONFIG.items():
                    tip_i    = cfg["tip"]
                    tx       = int(lm[tip_i].x * shared.WIN_W)
                    ty       = int(lm[tip_i].y * shared.WIN_H)
                    hand_key = (hand_label_str, fname)
                    state    = gesture._finger_states.get(hand_key)
                    vel      = 0.0
                    if state and state.get("y_history"):
                        vel = state.get("velocity", 0.0)
                    num_str = FINGER_NUM_LABEL[fname]
                    col     = FINGER_PRESSED_COL[fname] \
                        if vel >= gesture.PRESS_VEL_TH else (255, 255, 255)
                    lbl    = shared.font_small_bold.render(num_str, True, col)
                    shadow = shared.font_small_bold.render(num_str, True, (0, 0, 0))
                    cx = tx - lbl.get_width()  // 2
                    cy = ty - lbl.get_height() // 2
                    shared.screen.blit(shadow, (cx + 2, cy + 2))
                    shared.screen.blit(lbl,    (cx,     cy))

        r = ui.update_back_and_exit_timers(res, inhibit_back=False)
        if r == "BACK":
            return
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 로그인 화면 ──────────────────────────────────────────────────────
def login_screen():
    """손 제스처로 칸 선택 + 키보드 입력 → 로그인 또는 회원가입 후 shared.current_user 설정"""
    fields   = ["아이디", "비밀번호"]
    values   = ["", ""]
    focus    = 0
    message  = ""
    msg_col  = (255, 255, 255)

    # 가로 정렬: 라벨(왼) + 입력칸(오)
    LABEL_W  = 120
    BOX_W    = 340
    BOX_H    = 44
    GAP      = 16
    ROW_GAP  = 22
    ROW_Y0   = shared.WIN_H // 2 - 30
    ROW_YS   = [ROW_Y0 + i * (BOX_H + ROW_GAP) for i in range(len(fields))]
    BOX_X    = 480
    LBL_X    = BOX_X - GAP - LABEL_W

    _font = shared._font_bold(28)

    bg = None
    for _bg_path in ("assets/ui/login_bg.png", "assets/ui/mode_select_bg.png"):
        try:
            bg = pygame.image.load(_bg_path).convert_alpha()
            bg = pygame.transform.smoothscale(bg, (shared.WIN_W, shared.WIN_H))
            break
        except Exception:
            continue

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    focus = (focus + 1) % len(fields)
                elif event.key == pygame.K_BACKSPACE:
                    values[focus] = values[focus][:-1]
                elif event.key == pygame.K_RETURN:
                    username = values[0].strip()
                    password = values[1].strip()
                    if not username or not password:
                        message = "아이디와 비밀번호를 입력해주세요."
                        msg_col = (255, 100, 100)
                    elif auth.login(username, password):
                        shared.current_user = username
                        return
                    elif auth.register(username, password):
                        shared.current_user = username
                        message = f"'{username}' 계정이 생성되었습니다!"
                        msg_col = (100, 220, 100)
                        return
                    else:
                        message = "비밀번호가 틀렸습니다."
                        msg_col = (255, 100, 100)
                else:
                    if len(values[focus]) < 20:
                        values[focus] += event.unicode

        rgb, _ = gesture.cam_frame_rgb()
        if rgb is not None:
            ui.blit_camera_bg(rgb)
            res = shared.hands.process(rgb)
        else:
            shared.screen.fill((20, 20, 20))
            res = None

        if bg:
            shared.screen.blit(bg, (0, 0))

        # 손가락으로 입력칸 선택
        tip = gesture.get_index_tip_xy(res)
        for i, ry in enumerate(ROW_YS):
            box_rect = pygame.Rect(BOX_X, ry, BOX_W, BOX_H)
            if tip and box_rect.collidepoint(tip):
                focus = i

        _C = (30, 41, 57)  # #1E2939

        # 제목
        title_surf = _font.render("LOGIN", True, _C)
        shared.screen.blit(title_surf,
            (shared.WIN_W // 2 - title_surf.get_width() // 2, ROW_Y0 - 80))

        # 가로 정렬 입력 필드
        for i, (label, ry) in enumerate(zip(fields, ROW_YS)):
            # 라벨 (오른쪽 정렬로 박스에 붙임)
            lbl_surf = _font.render(label, True, _C)
            lbl_x = LBL_X + LABEL_W - lbl_surf.get_width()
            lbl_y = ry + (BOX_H - lbl_surf.get_height()) // 2
            shared.screen.blit(lbl_surf, (lbl_x, lbl_y))

            # 입력 박스 (흰색 배경)
            box_rect   = pygame.Rect(BOX_X, ry, BOX_W, BOX_H)
            border_col = (60, 160, 255) if focus == i else (180, 180, 180)
            pygame.draw.rect(shared.screen, (255, 255, 255), box_rect, border_radius=7)
            pygame.draw.rect(shared.screen, border_col, box_rect, 3, border_radius=7)

            display_val = "*" * len(values[i]) if i == 1 else values[i]
            val_surf = _font.render(display_val, True, _C)
            shared.screen.blit(val_surf, (box_rect.x + 12, box_rect.y + (BOX_H - val_surf.get_height()) // 2))

        # 안내문
        hint_surf = _font.render(
            "손가락으로 칸 선택  |  키보드 입력  |  Enter: 로그인 / 신규 자동 가입",
            True, _C)
        shared.screen.blit(hint_surf,
            (shared.WIN_W // 2 - hint_surf.get_width() // 2,
             ROW_YS[-1] + BOX_H + 30))

        # 메시지
        if message:
            msg_surf = _font.render(message, True, msg_col)
            shared.screen.blit(msg_surf,
                (shared.WIN_W // 2 - msg_surf.get_width() // 2,
                 ROW_YS[-1] + BOX_H + 68))

        # 손가락 커서
        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        pygame.display.flip()


# ── 최상위 모드 선택 및 실행 ─────────────────────────────────────────

def mode_select_and_run():
    login_screen()
    speak(
        "버츄얼 피아노 러닝 인터페이스에 온 걸 환영해요. "
        "자유연주, 따라연주, 도전연주 중 원하는 모드를 선택해주세요."
    )
    while True:
        mode = mode_select()

        if mode == "자유연주":
            free_play_loop()
        elif mode == "따라연주":
            score_practice_select()
        elif mode == "도전연주":
            challenge_practice_select()
