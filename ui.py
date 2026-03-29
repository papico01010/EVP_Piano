"""
ui.py - UI 렌더링 모듈
"""
import os
import sys
import math
import time
import numpy as np
import pygame
import shared
import gesture


# ── 피아노 베이스 이미지 캐시 ─────────────────────────────────────────
_piano_base_img = None   # basic_piano_st.png 스케일된 Surface


# ── 피아노 레이아웃 초기화 ────────────────────────────────────────────
def _init_piano_layout():
    global _piano_base_img
    n_white = len(shared.PIANO_WHITE_NOTES)  # 14 (2옥타브)

    shared.PIANO_W = int(shared.WIN_W * 0.85)
    shared.PIANO_H = int(shared.WIN_H * 0.42)
    shared.WHITE_W = shared.PIANO_W // n_white
    shared.WHITE_H = shared.PIANO_H
    shared.BLACK_W = int(shared.WHITE_W * 0.6)
    shared.BLACK_H = int(shared.WHITE_H * 0.62)

    shared.PIANO_X = (shared.WIN_W - shared.PIANO_W) // 2
    shared.PIANO_Y = (shared.WIN_H - shared.PIANO_H) // 2

    shared._piano_key_boxes.clear()

    for i, note in enumerate(shared.PIANO_WHITE_NOTES):
        x = shared.PIANO_X + i * shared.WHITE_W
        shared._piano_key_boxes[note] = pygame.Rect(
            x, shared.PIANO_Y, shared.WHITE_W - 2, shared.WHITE_H
        )

    black_positions = {
        "Cs4": 0,  "Ds4": 1,  "Fs4": 3,  "Gs4": 4,  "As4": 5,
        "Cs5": 7,  "Ds5": 8,  "Fs5": 10, "Gs5": 11, "As5": 12,
    }
    for note, white_idx in black_positions.items():
        x = shared.PIANO_X + white_idx * shared.WHITE_W + shared.WHITE_W - shared.BLACK_W // 2
        shared._piano_key_boxes[note] = pygame.Rect(
            x, shared.PIANO_Y, shared.BLACK_W, shared.BLACK_H
        )

    # 피아노 베이스 이미지 로드 (PIANO_W × PIANO_H 로 스케일)
    try:
        img = pygame.image.load("assets/basic_piano_st.png").convert_alpha()
        _piano_base_img = pygame.transform.smoothscale(
            img, (shared.PIANO_W, shared.PIANO_H)
        )
    except Exception:
        _piano_base_img = None


def _toggle_fullscreen():
    is_full = shared.screen.get_flags() & pygame.FULLSCREEN
    if is_full:
        shared.screen = pygame.display.set_mode(shared.CONFIG["win_size"], 0)
    else:
        shared.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    shared.WIN_W, shared.WIN_H = shared.screen.get_size()
    _init_piano_layout()


# ── 공통 이벤트 처리 ──────────────────────────────────────────────────
def handle_common_events():
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F2:
                shared.DEBUG_HITBOX["on"] = not shared.DEBUG_HITBOX["on"]
            elif e.key == pygame.K_F11:
                _toggle_fullscreen()
            elif e.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            elif e.key == pygame.K_F3:
                shared.DEBUG_HITBOX["press"] = not shared.DEBUG_HITBOX["press"]
            elif e.key == pygame.K_F4:
                shared.DEBUG_HITBOX["hyst"] = not shared.DEBUG_HITBOX["hyst"]


# ── 카메라 배경 ───────────────────────────────────────────────────────
def blit_camera_bg(rgb):
    surf = pygame.surfarray.make_surface(np.flipud(np.rot90(rgb)))
    surf = pygame.transform.scale(surf, (shared.WIN_W, shared.WIN_H))
    shared.screen.blit(surf, (0, 0))


# ── 텍스트/배너 렌더링 ────────────────────────────────────────────────
def draw_title_banner(title, top_pad=18):
    f      = shared.font_big
    label  = f.render(title, True, shared.COLORS["banner_fg"])
    shadow = f.render(title, True, shared.COLORS["text_shadow"])
    bw = label.get_width() + 40
    bh = label.get_height() + 24
    x  = shared.WIN_W // 2 - bw // 2
    y  = top_pad
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill(shared.COLORS["banner_bg"])
    shared.screen.blit(bg, (x, y))
    pygame.draw.rect(shared.screen, shared.COLORS["pill_outline"],
                     pygame.Rect(x, y, bw, bh), 3, 12)
    shared.screen.blit(shadow,
        (shared.WIN_W // 2 - label.get_width() // 2 + 3,
         y + (bh - label.get_height()) // 2 + 3))
    shared.screen.blit(label,
        (shared.WIN_W // 2 - label.get_width() // 2,
         y + (bh - label.get_height()) // 2))


def draw_lines_center(lines, y_start, size="mid", line_gap=18):
    f = {
        "huge":  shared.font_huge,
        "big":   shared.font_big,
        "mid":   shared.font_mid,
        "small": shared.font_small,
        "tiny":  shared.font_tiny,
        "micro": shared.font_micro,
    }[size]
    y = y_start
    for t in lines:
        lb = f.render(t, True, (255, 255, 255))
        sh = f.render(t, True, (0, 0, 0))
        shared.screen.blit(sh, (shared.WIN_W // 2 - lb.get_width() // 2 + 3, y + 3))
        shared.screen.blit(lb, (shared.WIN_W // 2 - lb.get_width() // 2, y))
        y += lb.get_height() + line_gap


def render_text_fit(text, max_w, base_size=66, min_size=30,
                    color=(255, 255, 255), shadow=True):
    size = base_size
    while size >= min_size:
        f = shared._font(size)
        w, _ = f.size(text)
        if w <= max_w:
            label = f.render(text, True, color)
            sh    = f.render(text, True, (0, 0, 0)) if shadow else None
            return label, sh, f
        size -= 2
    f   = shared._font(min_size)
    txt = text
    while f.size(txt + "…")[0] > max_w and len(txt) > 1:
        txt = txt[:-1]
    label = f.render(txt + "…", True, color)
    sh    = f.render(txt + "…", True, (0, 0, 0)) if shadow else None
    return label, sh, f


def timer_text(label, remain):
    try:
        r = max(0, int(math.ceil(remain)))
    except Exception:
        r = 0
    return f"{label}: {r}초"


def _draw_timer_fixed(text, corner="tr", pad=16, remain_secs=None):
    col = shared.COLORS["ok"]
    if remain_secs is not None:
        if remain_secs <= 2:
            col = shared.COLORS["crit"]
        elif remain_secs <= 5:
            col = shared.COLORS["warn"]
    pulse_alpha = 200
    if remain_secs is not None and remain_secs <= 2:
        pulse_alpha = int(180 + 75 * (0.5 + 0.5 * math.sin(time.time() * 2.5)))
    fnt = shared.font_mid if (remain_secs is not None and remain_secs <= 2) \
        else shared.font_small
    label  = fnt.render(text, True, col)
    shadow = fnt.render(text, True, shared.COLORS["text_shadow"])
    pad_x, pad_y = (24, 14) if fnt is shared.font_small else (28, 18)
    bw = label.get_width()  + pad_x * 2
    bh = label.get_height() + pad_y * 2
    if corner == "tr":
        x = shared.WIN_W - bw - pad; y = pad
    elif corner == "tl":
        x = pad; y = pad
    else:
        x = shared.WIN_W // 2 - bw // 2; y = pad
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill((0, 0, 0, pulse_alpha))
    shared.screen.blit(bg, (x, y))
    pygame.draw.rect(shared.screen, shared.COLORS["pill_outline"],
                     pygame.Rect(x, y, bw, bh), 3, 12)
    shared.screen.blit(shadow, (x + pad_x + 3, y + pad_y + 3))
    shared.screen.blit(label,  (x + pad_x,     y + pad_y))


def draw_badge_lines_above(rect, lines, gap=12, pad_x=14, pad_y=8):
    f       = shared.font_micro
    widths  = [f.size(t)[0] for t in lines]
    heights = [f.size(t)[1] for t in lines]
    w  = max(widths) + pad_x * 2
    h  = sum(heights) + pad_y * 2 + (gap if len(lines) > 1 else 0)
    x  = rect.x + (rect.width - w) // 2
    y  = rect.y - h - 12
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    shared.screen.blit(bg, (x, y))
    pygame.draw.rect(shared.screen, (255, 255, 255, 210),
                     pygame.Rect(x, y, w, h), 2, 10)
    cur_y = y + pad_y
    for t in lines:
        lb = f.render(t, True, (255, 255, 255))
        sh = f.render(t, True, (0, 0, 0))
        cx = x + (w - lb.get_width()) // 2
        shared.screen.blit(sh, (cx + 2, cur_y + 2))
        shared.screen.blit(lb, (cx,     cur_y))
        cur_y += lb.get_height() + (gap if t != lines[-1] else 0)


# ── 뒤로/종료 타이머 UI ───────────────────────────────────────────────
def update_back_and_exit_timers(result, *, inhibit_back=False,
                                 back_hold=None, exit_hold=None):
    if back_hold is None:
        back_hold = shared.CONFIG["back_hold"]
    if exit_hold is None:
        exit_hold = shared.CONFIG["exit_hold"]
    fists = gesture.detect_fist(result)
    now   = time.time()
    if fists >= 2:
        if gesture._exit_t["start"] is None:
            gesture._exit_t["start"] = now
        remain   = exit_hold - (now - gesture._exit_t["start"])
        sec_left = max(1, min(3, math.ceil(remain)))
        tim_img  = shared._exit_timer_imgs.get(sec_left)
        if tim_img:
            shared.screen.blit(tim_img, (shared.WIN_W - 320, 20))
        else:
            _draw_timer_fixed(timer_text("완전 종료까지", remain),
                              corner="tr", remain_secs=remain)
        if remain <= 0:
            gesture._exit_t["start"] = None
            gesture._back_t["start"] = None
            return "EXIT"
    else:
        gesture._exit_t["start"] = None
    if not inhibit_back and fists == 1:
        if gesture._back_t["start"] is None:
            gesture._back_t["start"] = now
        remain   = back_hold - (now - gesture._back_t["start"])
        sec_left = max(1, min(3, math.ceil(remain)))
        tim_img  = shared._back_timer_imgs.get(sec_left)
        if tim_img:
            shared.screen.blit(tim_img, (shared.WIN_W - 320, 20))
        else:
            _draw_timer_fixed(timer_text("뒤로", remain),
                              corner="tr", remain_secs=remain)
        if remain <= 0:
            gesture._back_t["start"] = None
            return "BACK"
    else:
        gesture._back_t["start"] = None
    return None


# ── 이미지 로드 헬퍼 ──────────────────────────────────────────────────
def load_first_existing(paths, size=None, fallback_rect=False):
    for p in paths:
        full = os.path.join("assets", p) if not p.startswith("assets") else p
        if os.path.exists(full):
            img = pygame.image.load(full).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, size)
            return img
    if fallback_rect:
        w, h = size if size else (int(shared.WIN_W * 0.3), int(shared.WIN_H * 0.2))
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 140))
        pygame.draw.rect(surf, (255, 255, 255, 220), surf.get_rect(), 3, 14)
        return surf
    return None


def load_button_image_pair(key, normal_path, active_path):
    try:
        normal = pygame.image.load(normal_path).convert_alpha()
        active = pygame.image.load(active_path).convert_alpha()
        shared.BTN_IMAGES[key] = {"normal": normal, "active": active}
    except Exception:
        shared.BTN_IMAGES[key] = {"normal": None, "active": None}


# ── 피아노 프로필 관련 ────────────────────────────────────────────────
def _load_full(path_rel, force_size=None):
    p = os.path.join(shared.ASSETS, path_rel)
    if not os.path.exists(p):
        raise FileNotFoundError(f"이미지 없음: {p}")
    img = pygame.image.load(p).convert()
    if force_size:
        img = pygame.transform.smoothscale(img, force_size)
    else:
        img = pygame.transform.smoothscale(img, (shared.WIN_W, shared.WIN_H))
    return img


def _note_base(n):
    return n[:-1] if n and n[-1].isdigit() else n


PRO48_CFG = {
    "left_margin_ratio":   0.012,
    "right_margin_ratio":  0.012,
    "top_margin_ratio":    0.04,
    "bottom_margin_ratio": 0.04,
    "row_gap_ratio":       0.02,
    "white_h_ratio_row":   0.95,
    "black_h_ratio_row":   0.62,
    "black_w_ratio":       0.62,
    "black_x_offset": {
        "Cs": 0.00, "Ds": 0.00, "Fs": 0.00, "Gs": 0.00, "As": 0.00,
    },
}

NOTES12_STD_UI = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]


def make_notes_48(start_oct=2, octaves=4):
    seq = []
    for oc in range(start_oct, start_oct + octaves):
        for n in NOTES12_STD_UI:
            seq.append(f"{n}{oc}")
    return seq


def build_key_layout_12(w, h, notes):
    boxes = {}
    top  = int(0.08 * h)
    h_w  = int(0.78 * h)
    h_bk = int(0.48 * h)
    w_w  = w / 7.0
    w_bk = w_w * 0.60
    xs   = [i * w_w for i in range(7)]
    for note, idx in [("C", 0), ("D", 1), ("E", 2), ("F", 3),
                      ("G", 4), ("A", 5), ("B", 6)]:
        full = f"{note}4"
        boxes[full] = pygame.Rect(int(xs[idx]), top, int(w_w), h_w)
    black_pairs = [("Cs", 0), ("Ds", 1), ("Fs", 3), ("Gs", 4), ("As", 5)]
    for note, i_white in black_pairs:
        full      = f"{note}4"
        center_x  = (i_white + 1.0) * w_w
        x         = int(center_x - w_bk / 2)
        boxes[full] = pygame.Rect(x, top, int(w_bk), h_bk)
    return boxes


def build_key_layout_48(w, h, notes, cfg=PRO48_CFG):
    boxes     = {}
    left      = int(cfg["left_margin_ratio"]  * w)
    right     = int(cfg["right_margin_ratio"] * w)
    usable_w  = w - left - right
    top_margin    = int(cfg["top_margin_ratio"]    * h)
    bottom_margin = int(cfg["bottom_margin_ratio"] * h)
    row_gap       = int(cfg["row_gap_ratio"]       * h)
    usable_h      = h - top_margin - bottom_margin - row_gap
    row_h         = usable_h // 2
    row_top_y = top_margin
    row_bot_y = top_margin + row_h + row_gap
    white_h   = int(row_h * cfg["white_h_ratio_row"])
    black_h   = int(row_h * cfg["black_h_ratio_row"])
    octaves   = [notes[i:i+12] for i in range(0, len(notes), 12)]
    if len(octaves) != 4:
        return boxes
    oct_w       = usable_w / 2.0
    white_order = ["C", "D", "E", "F", "G", "A", "B"]
    black_pairs = [("Cs", 0), ("Ds", 1), ("Fs", 3), ("Gs", 4), ("As", 5)]

    def place_oct(oct_notes, base_x, base_y):
        white_w = oct_w / 7.0
        black_w = white_w * cfg["black_w_ratio"]
        for idx, wn in enumerate(white_order):
            n = [nn for nn in oct_notes if nn[:-1] == wn][0]
            x = int(base_x + idx * white_w)
            boxes[n] = pygame.Rect(x, base_y, int(white_w), white_h)
        for k, i_white in black_pairs:
            n = [nn for nn in oct_notes if nn[:-1] == k]
            if not n:
                continue
            n        = n[0]
            center_x = base_x + (i_white + 1.0) * white_w
            dx       = cfg["black_x_offset"].get(k, 0.0) * white_w
            x        = int(center_x + dx - (black_w / 2))
            boxes[n] = pygame.Rect(x, base_y, int(black_w), black_h)

    place_oct(octaves[0], left + 0 * oct_w, row_top_y)
    place_oct(octaves[1], left + 1 * oct_w, row_top_y)
    place_oct(octaves[2], left + 0 * oct_w, row_bot_y)
    place_oct(octaves[3], left + 1 * oct_w, row_bot_y)
    return boxes


def pro_asset_key(note48):
    return note48


def _load_overlay(kind, note, mode):
    b     = _note_base(note)
    cands = []
    if mode == "easy":
        if kind == "user":
            cands = [f"user_push_{b}.png", f"ex_piano_user_input_{b}4.png"]
        else:
            cands = [f"program_push_{b}.png", f"ex_piano_program_input_{b}4.png"]
    else:
        if kind == "user":
            cands = [f"ex_piano_user_input_{note}.png"]
        else:
            cands = [f"ex_piano_program_input_{note}.png"]
    for nm in cands:
        try:
            return _load_full(nm)
        except Exception:
            continue
    return None


class PianoProfile:
    def __init__(self, name, notes, base_img_rel_candidates,
                 user_name_fn, prog_name_fn, key_layout_fn):
        self.name  = name
        self.notes = notes
        base_img   = None
        for rel in base_img_rel_candidates:
            try:
                base_img = _load_full(rel)
                break
            except Exception:
                continue
        if base_img is None:
            base_img = pygame.Surface((shared.WIN_W, shared.WIN_H))
            base_img.fill((240, 240, 240))
        self.base      = base_img
        self.user_imgs = {}
        self.prog_imgs = {}
        for n in notes:
            u = _load_overlay("user", user_name_fn(n), self.name)
            p = _load_overlay("prog", prog_name_fn(n), self.name)
            if u is not None: self.user_imgs[n] = u
            if p is not None: self.prog_imgs[n] = p
        self.key_boxes = key_layout_fn(shared.WIN_W, shared.WIN_H, notes)


def make_profiles():
    notes48   = make_notes_48(2, 4)
    notes12   = [f"{n}4" for n in NOTES12_STD_UI]
    prof_easy = PianoProfile(
        "easy", notes12,
        base_img_rel_candidates=[
            "basic_piano_st.png", "ex_piano_basic_st.png", "ex_piano_basic_12.png"
        ],
        user_name_fn=lambda n: n, prog_name_fn=lambda n: n,
        key_layout_fn=build_key_layout_12,
    )
    prof_pro = PianoProfile(
        "pro", notes48,
        base_img_rel_candidates=["ex_piano_basic_st.png", "basic_piano_st.png"],
        user_name_fn=pro_asset_key, prog_name_fn=pro_asset_key,
        key_layout_fn=build_key_layout_48,
    )
    return {"easy": prof_easy, "pro": prof_pro}


# ── 피아노 그리기 ─────────────────────────────────────────────────────
def is_black_name(n: str) -> bool:
    if not n: return False
    base = n[:-1] if n[-1].isdigit() else n
    return base in {"Cs", "Ds", "Fs", "Gs", "As"}


def _pro_row_metrics():
    cfg           = PRO48_CFG
    top_margin    = int(cfg["top_margin_ratio"]    * shared.WIN_H)
    bottom_margin = int(cfg["bottom_margin_ratio"] * shared.WIN_H)
    row_gap       = int(cfg["row_gap_ratio"]       * shared.WIN_H)
    usable_h = shared.WIN_H - top_margin - bottom_margin - row_gap
    row_h    = usable_h // 2
    row_top_y = top_margin
    row_bot_y = top_margin + row_h + row_gap
    black_h   = int(row_h * cfg["black_h_ratio_row"])
    return row_top_y, row_bot_y, row_h, black_h


def pro_octave_from_xy(full_note_str, x, y):
    base12 = full_note_str[:-1] if full_note_str[-1].isdigit() else full_note_str
    row_top_y, row_bot_y, row_h, _ = _pro_row_metrics()
    in_top_row = (row_top_y <= y < row_top_y + row_h)
    in_right   = (x >= shared.WIN_W / 2)
    if in_top_row and not in_right:
        octave = 3
    elif in_top_row and in_right:
        octave = 4
    elif (not in_top_row) and not in_right:
        octave = 5
    else:
        octave = 6
    return base12, octave


def draw_piano_profile(user_note=None, program_note=None,
                       user_notes=None, alpha=50):
    if not shared._piano_key_boxes:
        _init_piano_layout()

    notes_to_draw = set()
    if user_notes:
        notes_to_draw.update(user_notes)
    if user_note:
        notes_to_draw.add(user_note)

    # ── 피아노 베이스 이미지 ──────────────────────────────────────────
    if _piano_base_img is not None:
        shared.screen.blit(_piano_base_img, (shared.PIANO_X, shared.PIANO_Y))
    else:
        # 이미지 없을 때 폴백: 어두운 배경 rect
        bg = pygame.Surface((shared.PIANO_W + 10, shared.PIANO_H + 10), pygame.SRCALPHA)
        bg.fill((30, 30, 30, 80))
        shared.screen.blit(bg, (shared.PIANO_X - 5, shared.PIANO_Y - 5))

    # ── 흰 건반 눌림 하이라이트 ──────────────────────────────────────
    for note in shared.PIANO_WHITE_NOTES:
        r = shared._piano_key_boxes[note]
        if note == program_note:
            col = (60, 220, 100, 160)
        elif note in notes_to_draw:
            col = (80, 160, 255, 160)
        else:
            continue
        s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        s.fill(col)
        shared.screen.blit(s, r.topleft)

    # ── 검은 건반 눌림 하이라이트 ────────────────────────────────────
    for note in shared.PIANO_BLACK_NOTES:
        r = shared._piano_key_boxes[note]
        if note == program_note:
            col = (60, 200, 80, 180)
        elif note in notes_to_draw:
            col = (40, 100, 220, 180)
        else:
            continue
        s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        s.fill(col)
        shared.screen.blit(s, r.topleft)


def draw_note_banner(text):
    if not text:
        return
    pad_x, pad_y = 32, 18
    fnt    = shared.font_mid
    label  = fnt.render(text, True, (255, 255, 255))
    shadow = fnt.render(text, True, shared.COLORS["text_shadow"])
    bw = label.get_width()  + pad_x * 2
    bh = label.get_height() + pad_y * 2
    x  = shared.WIN_W // 2 - bw // 2
    y  = shared.WIN_H - bh - 28
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill(shared.COLORS["pill_bg"])
    shared.screen.blit(bg, (x, y))
    pygame.draw.rect(shared.screen, shared.COLORS["pill_outline"],
                     pygame.Rect(x, y, bw, bh), 3, 14)
    pygame.draw.circle(shared.screen, shared.COLORS["accent"],
                       (x + 18, y + bh // 2), 6)
    shared.screen.blit(shadow, (x + pad_x + 3, y + pad_y + 3))
    shared.screen.blit(label,  (x + pad_x,     y + pad_y))


def draw_hitbox_overlay():
    if not shared.DEBUG_HITBOX.get("hitbox"):
        return
    if not shared._piano_key_boxes:
        return
    for note, r in shared._piano_key_boxes.items():
        is_black = note in shared.PIANO_BLACK_NOTES
        col = (80, 80, 255) if is_black else (255, 255, 80)
        pygame.draw.rect(shared.screen, col, r, 2)
        lb = shared.font_micro.render(note, True, col)
        shared.screen.blit(lb, (r.x + 2, r.y + 2))


def _draw_text_line(x, y, txt,
                    f=pygame.font.SysFont(None, 28),
                    col=(255, 255, 255)):
    lb = f.render(txt, True, col)
    sh = f.render(txt, True, (0, 0, 0))
    shared.screen.blit(sh, (x + 2, y + 2))
    shared.screen.blit(lb, (x,     y))
    return y + lb.get_height() + 6


# ── 디버그 패널 ───────────────────────────────────────────────────────
def draw_press_panel():
    if not shared.DEBUG_HITBOX.get("press"):
        return

    FINGER_ORDER = ["pinky", "ring", "middle", "index", "thumb"]
    FINGER_NUM   = {"pinky": "5", "ring": "4", "middle": "3",
                    "index": "2", "thumb": "1"}
    HAND_LABELS  = ["left", "right"]
    HAND_KR      = {"left": "왼손", "right": "오른손"}

    panel_w = 188
    panel_h = 168
    pad_x   = 16
    gap     = 8

    for hi, hand_label in enumerate(HAND_LABELS):
        x = pad_x + hi * (panel_w + gap)
        y = 16

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 10, 10, 200))
        pygame.draw.rect(panel, (180, 180, 180, 220), panel.get_rect(), 1, 8)

        hand_kr = HAND_KR[hand_label]
        lb_head = shared.font_micro.render(hand_kr, True, (220, 220, 220))
        panel.blit(lb_head,
                   (panel_w // 2 - lb_head.get_width() // 2, 5))
        pygame.draw.line(panel, (90, 90, 90), (8, 26), (panel_w - 8, 26), 1)

        row_h = (panel_h - 30) // 5

        for fi, fname in enumerate(FINGER_ORDER):
            hand_key = (hand_label, fname)
            state    = gesture._finger_states.get(hand_key)
            num      = FINGER_NUM[fname]
            cy       = 28 + fi * row_h

            if state and state["y_history"]:
                vel     = state.get("velocity", 0.0)
                pressed = state["pressed"]
                need_r  = state.get("needs_reset", False)
                locked  = state.get("locked_note") or ""
            else:
                vel = 0.0; pressed = False; need_r = False; locked = ""

            if need_r:
                txt_col = (255, 165, 0);   tag = "WAIT"
            elif pressed:
                txt_col = (60, 230, 110);  tag = locked if locked else "ON"
            elif vel >= gesture.PRESS_VEL_TH:
                txt_col = (255, 255, 60);  tag = "↓HIT"
            else:
                txt_col = (140, 140, 140); tag = "OFF"

            vel_str = f"{vel:+.3f}"
            line    = f"{num}  {vel_str}  {tag}"
            lb      = shared.font_micro.render(line, True, txt_col)

            max_w = panel_w - 16
            if lb.get_width() > max_w:
                lb = pygame.transform.smoothscale(lb, (max_w, lb.get_height()))
            panel.blit(lb, (10, cy + (row_h - lb.get_height()) // 2))

        shared.screen.blit(panel, (x, y))


def draw_hysteresis_scope():
    if not shared.DEBUG_HITBOX.get("hyst"):
        return

    active = {k: v for k, v in gesture._finger_states.items()
              if v["y_history"]}
    if not active:
        return

    FINGER_KR = {"thumb": "엄지", "index": "검지", "middle": "중지",
                 "ring":  "약지", "pinky": "소지"}
    HAND_KR   = {"left": "왼", "right": "오른",
                 "hand0": "손0", "hand1": "손1"}

    cols  = 2
    sw, sh = 260, 100
    pad   = 6
    items = list(sorted(active.items()))

    total_w = cols * (sw + pad) + pad
    base_x  = shared.WIN_W - total_w - 10
    base_y  = 10

    for i, ((hand_label, fname), state) in enumerate(items):
        ci = i % cols
        ri = i // cols
        sx = base_x + pad + ci * (sw + pad)
        sy = base_y + pad + ri * (sh + pad)

        pressed = state["pressed"]
        need_r  = state.get("needs_reset", False)
        locked  = state.get("locked_note") or ""
        vel     = state.get("velocity", 0.0)

        if need_r:
            border_col = (255, 165, 0)
        elif pressed:
            border_col = (60, 230, 110)
        else:
            border_col = (100, 100, 100)

        panel = pygame.Surface((sw, sh), pygame.SRCALPHA)
        panel.fill((10, 10, 10, 200))
        pygame.draw.rect(panel, (*border_col, 230), panel.get_rect(), 2, 6)

        graph = pygame.Rect(8, 20, sw - 16, sh - 28)
        pygame.draw.rect(panel, (30, 30, 30, 200), graph)
        pygame.draw.rect(panel, (60, 60, 60, 200), graph, 1)

        series = list(state["y_history"])
        if len(series) > 1:
            y_min   = min(series) - 0.01
            y_max   = max(series) + 0.01
            y_range = max(y_max - y_min, 0.01)
            pts     = []
            mx      = max(1, len(series) - 1)
            for j, v in enumerate(series):
                px = graph.x + int(graph.w * (j / mx))
                py = graph.y + int(graph.h * (1.0 - (v - y_min) / y_range))
                pts.append((px, py))
            for j in range(1, len(pts)):
                pygame.draw.line(panel, (255, 220, 60), pts[j-1], pts[j], 2)

        f_lbl     = pygame.font.SysFont(None, 20)
        hand_kr   = HAND_KR.get(hand_label, hand_label)
        finger_kr = FINGER_KR.get(fname, fname)
        title     = f"{hand_kr}{finger_kr}"
        if locked:
            title += f"  [{locked}]"
        lb = f_lbl.render(title, True, border_col)
        panel.blit(lb, (8, 3))

        vel_lb = f_lbl.render(f"v:{vel:+.3f}", True, (200, 200, 200))
        panel.blit(vel_lb, (sw - vel_lb.get_width() - 6, 3))

        shared.screen.blit(panel, (sx, sy))


def draw_and_debug(user_note=None, program_note=None,
                   note_label_text=None, user_notes=None):
    draw_piano_profile(
        user_note=user_note,
        program_note=program_note,
        user_notes=user_notes,
    )
    draw_press_panel()
    draw_hysteresis_scope()
    draw_hitbox_overlay()
    if note_label_text:
        draw_note_banner(note_label_text)
