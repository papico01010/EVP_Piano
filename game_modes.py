"""
game_modes.py - 게임 플로우 모듈
"""
import pyttsx3
import sys
import math
import time
import threading
import pygame

import shared
import audio
import gesture
import ui


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


def _load_image_cache():
    """SONGS 키를 참고해 관련 이미지를 미리 로드한다."""
    global _title_imgs, _note_imgs, _score_imgs

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

    import pyttsx3
    import threading

    def _speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            engine.say(tts_msg)
            engine.runAndWait()
        except Exception:
            pass

    threading.Thread(target=_speak, daemon=True).start()

    try:
        img = pygame.image.load(f"assets/ui/{img_key}.png").convert_alpha()
        img = pygame.transform.smoothscale(img, (shared.WIN_W, shared.WIN_H))
    except Exception as e:
        print(f"confirm 이미지 로드 실패: {e}")
        img = None

    ans = yes_no_screen("", hold_sec=1, bg_img=img)
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
        "pinky":  (255, 100, 100),
        "ring":   (255, 180,  60),
        "middle": ( 80, 220, 100),
        "index":  ( 60, 200, 255),
        "thumb":  (200, 100, 255),
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
                    lbl    = shared.font_small.render(num_str, True, col)
                    shadow = shared.font_small.render(num_str, True, (0, 0, 0))
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

    song_imgs = {}
    for _name in song_names:
        try:
            _n = pygame.image.load(f"assets/ui/song_{_name}_normal.png").convert_alpha()
            _a = pygame.image.load(f"assets/ui/song_{_name}_active.png").convert_alpha()
            song_imgs[_name] = {"normal": _n, "active": _a}
        except Exception:
            song_imgs[_name] = {"normal": None, "active": None}

    selected     = None
    select_start = None
    hold_sec     = 1

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

        btn_w   = int(shared.WIN_W * 0.25)
        btn_h   = int(shared.WIN_H * 0.13)
        gap     = int(shared.WIN_H * 0.02)
        start_y = int(shared.WIN_H * 0.23)

        hovered = None
        col_x   = [int(shared.WIN_W * 0.15), int(shared.WIN_W * 0.55)]
        for i, name in enumerate(song_names):
            col = i // 5
            row = i % 5
            x   = col_x[col]
            y   = start_y + row * (btn_h + gap)
            r   = pygame.Rect(x, y, btn_w, btn_h)
            img_set = song_imgs.get(name)
            if img_set and img_set.get("normal") and img_set.get("active"):
                state    = "active" if (tip and r.collidepoint(tip)) else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(base_img, (r.width, r.height))
                shared.screen.blit(scaled, r.topleft)
            else:
                c = (100, 180, 255) if (tip and r.collidepoint(tip)) else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, r, border_radius=8)
                lbl = shared.font_micro.render(name, True, (255, 255, 255))
                shared.screen.blit(
                    lbl, (r.centerx - lbl.get_width()  // 2,
                          r.centery - lbl.get_height() // 2)
                )
            if tip and r.collidepoint(tip):
                hovered = name

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        if hovered:
            if selected != hovered:
                selected     = hovered
                select_start = time.time()
            else:
                el       = time.time() - select_start

                if el >= hold_sec:
                    song_practice_flow(selected)
                    selected     = None
                    select_start = None
        else:
            selected     = None
            select_start = None

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(hovered))
        if r == "BACK":
            return
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 따라연주 플로우 ───────────────────────────────────────────────────
def song_practice_flow(song_name):
    melody_12  = [_n7_to_12(n) for n in audio.SONGS[song_name]]
    play_delay = select_play_speed()
    res        = None

    for n12 in melody_12:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is not None:
            res = shared.hands.process(rgb)
            ui.blit_camera_bg(rgb)
            prog_note_overlay = f"{n12}4"

            _t_img = _title_imgs.get(f"follow_{song_name}")
            if _t_img:
                shared.screen.blit(_t_img, (shared.WIN_W // 2 - 250, 18))
            else:
                ui.draw_title_banner(f"따라 연주: {song_name}", top_pad=18)

            ui.draw_and_debug(
                user_note=None,
                program_note=prog_note_overlay,
                note_label_text=note_to_kor(f"{n12}4"),
            )
            ui.draw_lines_center(
                [f"현재 음: {note_to_kor(n12+'4')}"], 116, size="small", line_gap=8
            )
            r = ui.update_back_and_exit_timers(res, inhibit_back=False)
            if r == "BACK":
                return "back_to_practice_menu"
            if r == "EXIT":
                pygame.quit(); sys.exit()
            pygame.display.flip()
        audio.get_sound(n12, 4).play().fadeout(350)
        time.sleep(play_delay)

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
        "pinky":  (255, 100, 100),
        "ring":   (255, 180,  60),
        "middle": ( 80, 220, 100),
        "index":  ( 60, 200, 255),
        "thumb":  (200, 100, 255),
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
        target12    = melody_12[idx]
        target_note = f"{target12}4"
        if target_note in pressed_notes:
            nh.update(True, target12, 4)
            note_label = note_to_kor(target_note)
        else:
            nh.update(False, None, None)

        ui.blit_camera_bg(rgb)

        _t_img = _title_imgs.get(f"follow_{song_name}")
        if _t_img:
            shared.screen.blit(_t_img, (shared.WIN_W // 2 - 250, 18))
        else:
            ui.draw_title_banner(f"따라 연주: {song_name}", top_pad=18)

        prog_overlay = f"{melody_12[idx]}4" if idx < len(melody_12) else None
        ui.draw_and_debug(
            user_notes=pressed_notes,
            program_note=prog_overlay,
            note_label_text=None,
        )
        _sc = _score_imgs.get(song_name)
        if _sc:
            shared.screen.blit(
                _sc, (shared.WIN_W // 2 - int(shared.WIN_W * 0.3),
                      shared.WIN_H - int(229 * 0.8))
            )

        if idx < len(melody_12):
            _kor   = note_to_kor(melody_12[idx] + '4')
            _n_img = _note_imgs.get(_kor)
            if _n_img:
                shared.screen.blit(_n_img, (shared.WIN_W // 2 - 100,
                                            int(shared.WIN_H * 0.68)))
            else:
                ui.draw_lines_center(
                    [f"쳐야 하는 음: {_kor}"],
                    int(shared.WIN_H * 0.68), size="small", line_gap=8,
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
                    lbl    = shared.font_small.render(num_str, True, col)
                    shadow = shared.font_small.render(num_str, True, (0, 0, 0))
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
            if idx >= len(melody_12):
                nh.reset()
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
                    if finish_title_img:
                        shared.screen.blit(
                            finish_title_img,
                            (shared.WIN_W // 2 - int(shared.WIN_W * 0.30),
                             int(shared.WIN_H * 0.03))
                        )
                    else:
                        ui.draw_title_banner("잘 했어요!", top_pad=18)
                    if finish_guide_img:
                        shared.screen.blit(
                            finish_guide_img,
                            (shared.WIN_W // 2 - int(shared.WIN_W * 0.25),
                             shared.WIN_H // 2 - int(shared.WIN_H * 0.1))
                        )
                    else:
                        ui.draw_lines_center(
                            ["'다시하기' 또는 '악보선택'이라고 말해요"],
                            shared.WIN_H // 2 - 40, size="small", line_gap=10,
                        )
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

    song_imgs = {}
    for _name in song_names:
        try:
            _n = pygame.image.load(
                f"assets/ui/song_{_name}_normal.png"
            ).convert_alpha()
            _a = pygame.image.load(
                f"assets/ui/song_{_name}_active.png"
            ).convert_alpha()
            song_imgs[_name] = {"normal": _n, "active": _a}
        except Exception:
            song_imgs[_name] = {"normal": None, "active": None}

    selected     = None
    select_start = None
    hold_sec     = 1

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

        btn_w   = int(shared.WIN_W * 0.25)
        btn_h   = int(shared.WIN_H * 0.13)
        gap     = int(shared.WIN_H * 0.02)
        start_y = int(shared.WIN_H * 0.23)

        hovered = None
        col_x   = [int(shared.WIN_W * 0.15), int(shared.WIN_W * 0.55)]
        for i, name in enumerate(song_names):
            col = i // 5
            row = i % 5
            x   = col_x[col]
            y   = start_y + row * (btn_h + gap)
            r   = pygame.Rect(x, y, btn_w, btn_h)
            img_set = song_imgs.get(name)
            if img_set and img_set.get("normal") and img_set.get("active"):
                state    = "active" if (tip and r.collidepoint(tip)) else "normal"
                base_img = img_set[state]
                scaled   = pygame.transform.smoothscale(base_img, (r.width, r.height))
                shared.screen.blit(scaled, r.topleft)
            else:
                c = (100, 180, 255) if (tip and r.collidepoint(tip)) else (60, 60, 60)
                pygame.draw.rect(shared.screen, c, r, border_radius=8)
                lbl = shared.font_micro.render(name, True, (255, 255, 255))
                shared.screen.blit(
                    lbl, (r.centerx - lbl.get_width()  // 2,
                          r.centery - lbl.get_height() // 2)
                )
            if tip and r.collidepoint(tip):
                hovered = name

        if tip:
            if shared._tip_img:
                shared.screen.blit(shared._tip_img, (tip[0] - 40, tip[1] - 40))
            else:
                pygame.draw.circle(shared.screen, (255, 255, 0), tip, 12, 0)

        if hovered:
            if selected != hovered:
                selected     = hovered
                select_start = time.time()
            else:
                el       = time.time() - select_start

                if el >= hold_sec:
                    challenge_practice_flow(selected)
                    selected     = None
                    select_start = None
        else:
            selected     = None
            select_start = None

        r = ui.update_back_and_exit_timers(res, inhibit_back=bool(hovered))
        if r == "BACK":
            return
        if r == "EXIT":
            pygame.quit(); sys.exit()

        pygame.display.flip()


# ── 도전연주 플로우 ───────────────────────────────────────────────────
def challenge_practice_flow(song_name):
    melody_12  = [_n7_to_12(n) for n in audio.SONGS[song_name]]
    play_delay = select_play_speed()

    for n12 in melody_12:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is not None:
            res = shared.hands.process(rgb)
            ui.blit_camera_bg(rgb)
            _t_img = _title_imgs.get(f"challenge_{song_name}")
            if _t_img:
                shared.screen.blit(_t_img, (shared.WIN_W // 2 - 250, 18))
            else:
                ui.draw_title_banner(f"도전연주: {song_name}", top_pad=18)
            ui.draw_and_debug(
                user_note=None,
                program_note=f"{n12}4",
                note_label_text=None,
            )
            ui.draw_lines_center(
                ["잘 들어봐요! 외워서 쳐야 해요."], 116, size="small", line_gap=8
            )
            r = ui.update_back_and_exit_timers(res, inhibit_back=False)
            if r == "BACK":
                return
            if r == "EXIT":
                pygame.quit(); sys.exit()
            pygame.display.flip()
        audio.get_sound(n12, 4).play().fadeout(350)
        time.sleep(play_delay)

    # 준비 카운트다운 3초
    countdown_start = time.time()
    while time.time() - countdown_start < 3:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)
        ui.blit_camera_bg(rgb)
        remain = 3 - (time.time() - countdown_start)
        ui.draw_title_banner("준비하세요!", top_pad=18)
        ui.draw_lines_center(
            [str(int(math.ceil(remain)))],
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
        "pinky":  (255, 100, 100),
        "ring":   (255, 180,  60),
        "middle": ( 80, 220, 100),
        "index":  ( 60, 200, 255),
        "thumb":  (200, 100, 255),
    }

    while True:
        ui.handle_common_events()
        rgb, _ = gesture.cam_frame_rgb()
        if rgb is None:
            continue
        res = shared.hands.process(rgb)

        pressed_notes = gesture.get_all_pressed_notes(res)
        gesture.is_index_press(res)

        target12    = melody_12[idx]
        target_note = f"{target12}4"

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
        if idx >= len(melody_12):
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

            result_start = time.time()
            while time.time() - result_start < 5:
                ui.handle_common_events()
                rgb, _ = gesture.cam_frame_rgb()
                if rgb is None:
                    continue
                res = shared.hands.process(rgb)
                ui.blit_camera_bg(rgb)
                ui.draw_title_banner("결과 발표!", top_pad=18)
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
                finish_title_img = pygame.image.load(
                    "assets/ui/finish_title.png"
                ).convert_alpha()
                finish_title_img = pygame.transform.smoothscale(
                    finish_title_img,
                    (int(shared.WIN_W * 0.3), int(shared.WIN_H * 0.2))
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
                if finish_guide_img:
                    shared.screen.blit(
                        finish_guide_img,
                        (shared.WIN_W // 2 - int(shared.WIN_W * 0.25),
                         shared.WIN_H // 2 - int(shared.WIN_H * 0.1))
                    )
                else:
                    ui.draw_lines_center(
                        ["'다시하기' 또는 '악보선택'이라고 말해요"],
                        shared.WIN_H // 2 - 40, size="small", line_gap=10,
                    )
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

        _t_img = _title_imgs.get(f"challenge_{song_name}")
        if _t_img:
            shared.screen.blit(_t_img, (shared.WIN_W // 2 - 250, 18))
        else:
            ui.draw_title_banner(f"도전연주: {song_name}", top_pad=18)

        ui.draw_and_debug(
            user_notes=pressed_notes,
            program_note=None,
            note_label_text=None,
        )
        _sc = _score_imgs.get(song_name)
        if _sc:
            shared.screen.blit(
                _sc, (shared.WIN_W // 2 - int(shared.WIN_W * 0.3),
                      shared.WIN_H - int(229 * 0.8))
            )

        if time.time() < wrong_display_until and wrong_notes:
            overlay = pygame.Surface((shared.WIN_W, shared.WIN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))
            shared.screen.blit(overlay, (0, 0))
            for note in wrong_notes:
                if note in shared._piano_key_boxes:
                    r_box = shared._piano_key_boxes[note]
                    s = pygame.Surface((r_box.width, r_box.height), pygame.SRCALPHA)
                    s.fill((255, 60, 60, 200))
                    shared.screen.blit(s, r_box.topleft)
                    pygame.draw.rect(shared.screen, (255, 0, 0), r_box, 2)
            ui.draw_lines_center(
                ["틀렸어요. 다음 음을 치세요!"],
                shared.WIN_H // 2 - 40, size="mid", line_gap=0,
            )
        else:
            wrong_notes = set()

        score_text = (
            f"정확도: {int((correct/total)*100) if total > 0 else 0}%"
            f"  ({correct}/{total})"
        )
        ui.draw_lines_center(
            [score_text, f"남은 음: {len(melody_12)-idx}개"],
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
                    lbl    = shared.font_small.render(num_str, True, col)
                    shadow = shared.font_small.render(num_str, True, (0, 0, 0))
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


# ── 최상위 모드 선택 및 실행 ─────────────────────────────────────────
def mode_select_and_run():
    while True:
        mode = mode_select()
        if mode == "BACK_TO_DIFFICULTY":
            return "BACK_TO_DIFFICULTY"
        if mode == "자유연주":
            free_play_loop()
        elif mode == "따라연주":
            score_practice_select()
        elif mode == "도전연주":
            challenge_practice_select()
