"""
gesture.py - 손 제스처 인식 모듈
"""
import math
import time
import numpy as np
import cv2
from collections import deque
import shared

# ── 임계값 상수 ───────────────────────────────────────────────────────
PRESS_TH, REL_TH = 0.40, 0.25

MULTI_PRESS_TH    = 0.30
MULTI_REL_TH      = 0.12
OVERLAP_THRESHOLD = 40
EXTEND_TH         = 0.08

PRESS_VEL_TH   = 0.012
MIN_BEND_TH    = 0.15
RELEASE_VEL_TH = -0.003
VEL_FRAMES     = 3
PRESS_COOLDOWN = 0 # 같은 음 연주시 씹힘 조정

# ── 손가락 랜드마크 인덱스 설정 ───────────────────────────────────────
FINGER_CONFIG = {
    "thumb":  {"tip": 4,  "ip":  3, "mcp": 2,  "cmc": 1},
    "index":  {"tip": 8,  "dip": 7, "pip": 6,  "mcp": 5},
    "middle": {"tip": 12, "dip": 11, "pip": 10, "mcp": 9},
    "ring":   {"tip": 16, "dip": 15, "pip": 14, "mcp": 13},
    "pinky":  {"tip": 20, "dip": 19, "pip": 18, "mcp": 17},
}

# ── 손가락별 임계값 ───────────────────────────────────────────────────
FINGER_PRESS_TH = {
    "index":  0.28,
    "middle": 0.32,
    "ring":   0.42,
    "pinky":  0.22,
    "thumb":  0.30,
}
FINGER_REL_TH = {
    "index":  0.10,
    "middle": 0.12,
    "ring":   0.18,
    "pinky":  0.12,
    "thumb":  0.10,
}

# 연쇄 보정 계수
COUPLING_RULES = [
    ("ring",   "pinky",  0.50),
    ("ring",   "middle", 0.35),
    ("middle", "ring",   0.20),
]

VELOCITY_WINDOW = 5
VELOCITY_MIN_TH = 0.012

# ── 전역 제스처 상태 ──────────────────────────────────────────────────
_press_scores: deque = deque(maxlen=20)
_press_state: dict   = {"pressed": False}
_finger_states: dict = {}
_wrist_y_history: dict = {}

# ── 종료 타이머 상태 (ui.py에서도 참조) ──────────────────────────────
_back_t = {"start": None}
_exit_t = {"start": None}


# ── 카메라 프레임 획득 ────────────────────────────────────────────────
def cam_frame_rgb():
    ret, f = shared.cam.read()
    if not ret:
        return None, None
    rgb = cv2.cvtColor(cv2.flip(f, 1), cv2.COLOR_BGR2RGB)
    return rgb, f


def get_index_tip_xy(result):
    if not (result and result.multi_hand_landmarks):
        return None
    lm = result.multi_hand_landmarks[0].landmark
    return int(lm[8].x * shared.WIN_W), int(lm[8].y * shared.WIN_H)


# ── 굽힘 점수 계산 ────────────────────────────────────────────────────
def _bend_score_finger_raw(lm, tip_i, dip_i, pip_i, mcp_i, tilt_deg=0.0) -> float:
    if tip_i == 20:   # 소지
        ANG_HI, ANG_LO = 172.0, 140.0
        LEN_HI, LEN_LO = 0.32, 0.08
    elif tip_i == 16:  # 약지
        ANG_HI, ANG_LO = 172.0, 138.0
        LEN_HI, LEN_LO = 0.34, 0.09
    else:
        ANG_HI, ANG_LO = 175.0, 110.0
        LEN_HI, LEN_LO = 0.45, 0.15
    W_ANG, W_LEN = 0.6, 0.4

    mcp = (int(lm[mcp_i].x * shared.WIN_W), int(lm[mcp_i].y * shared.WIN_H))
    pip = (int(lm[pip_i].x * shared.WIN_W), int(lm[pip_i].y * shared.WIN_H))
    dip = (int(lm[dip_i].x * shared.WIN_W), int(lm[dip_i].y * shared.WIN_H))
    tip = (int(lm[tip_i].x * shared.WIN_W), int(lm[tip_i].y * shared.WIN_H))

    def _angle(a, b, c):
        ab = (a[0] - b[0], a[1] - b[1])
        cb = (c[0] - b[0], c[1] - b[1])
        lab = math.hypot(*ab); lcb = math.hypot(*cb)
        if lab < 1e-6 or lcb < 1e-6:
            return 180.0
        cosv = max(-1.0, min(1.0, (ab[0]*cb[0]+ab[1]*cb[1]) / (lab*lcb)))
        return math.degrees(math.acos(cosv))

    pip_ang = _angle(mcp, pip, dip)
    dip_ang = _angle(pip, dip, tip)

    tilt_factor = abs(math.sin(math.radians(tilt_deg))) * 15.0
    adj_ang_lo  = ANG_LO + tilt_factor

    wrist    = (int(lm[0].x * shared.WIN_W), int(lm[0].y * shared.WIN_H))
    mid_mcp  = (int(lm[9].x * shared.WIN_W), int(lm[9].y * shared.WIN_H))
    hand_scale = max(1.0, math.hypot(mid_mcp[0]-wrist[0], mid_mcp[1]-wrist[1]))
    len_ratio  = math.hypot(tip[0]-pip[0], tip[1]-pip[1]) / hand_scale

    def remap(v, hi, lo):
        if v >= hi: return 0.0
        if v <= lo: return 1.0
        return (hi - v) / (hi - lo)

    ang_score = max(remap(pip_ang, ANG_HI, adj_ang_lo),
                    remap(dip_ang, ANG_HI, adj_ang_lo))
    len_score = remap(len_ratio, LEN_HI, LEN_LO)
    return W_ANG * ang_score + W_LEN * len_score


def get_hand_tilt(lm) -> float:
    """손목(0)~중지MCP(9) 벡터로 손 기울기 각도(도) 반환 → 카메라 각도 보정용"""
    dx = lm[9].x - lm[0].x
    dy = lm[9].y - lm[0].y
    return math.degrees(math.atan2(dy, dx))


def _bend_score_finger(lm, tip_i, dip_i, pip_i, mcp_i, tilt_deg=0.0) -> float:
    """
    검지~소지 굽힘 점수 계산 (0.0 ~ 1.0)
    tilt_deg: 손 기울기 → 각도 임계값을 동적으로 보정
    """
    ANG_HI, ANG_LO = 175.0, 110.0
    LEN_HI, LEN_LO = 0.45, 0.15
    W_ANG,  W_LEN  = 0.6,  0.4

    mcp = (int(lm[mcp_i].x * shared.WIN_W), int(lm[mcp_i].y * shared.WIN_H))
    pip = (int(lm[pip_i].x * shared.WIN_W), int(lm[pip_i].y * shared.WIN_H))
    dip = (int(lm[dip_i].x * shared.WIN_W), int(lm[dip_i].y * shared.WIN_H))
    tip = (int(lm[tip_i].x * shared.WIN_W), int(lm[tip_i].y * shared.WIN_H))

    def _angle(a, b, c):
        ab = (a[0]-b[0], a[1]-b[1])
        cb = (c[0]-b[0], c[1]-b[1])
        lab = math.hypot(*ab); lcb = math.hypot(*cb)
        if lab < 1e-6 or lcb < 1e-6:
            return 180.0
        cosv = max(-1.0, min(1.0, (ab[0]*cb[0]+ab[1]*cb[1]) / (lab*lcb)))
        return math.degrees(math.acos(cosv))

    pip_ang = _angle(mcp, pip, dip)
    dip_ang = _angle(pip, dip, tip)

    tilt_factor = abs(math.sin(math.radians(tilt_deg))) * 15.0
    adj_ang_lo  = ANG_LO + tilt_factor

    wrist   = (int(lm[0].x * shared.WIN_W), int(lm[0].y * shared.WIN_H))
    mid_mcp = (int(lm[9].x * shared.WIN_W), int(lm[9].y * shared.WIN_H))
    hand_scale = max(1.0, math.hypot(mid_mcp[0]-wrist[0], mid_mcp[1]-wrist[1]))
    len_ratio  = math.hypot(tip[0]-pip[0], tip[1]-pip[1]) / hand_scale

    def remap(v, hi, lo):
        if v >= hi: return 0.0
        if v <= lo: return 1.0
        return (hi - v) / (hi - lo)

    ang_score = max(remap(pip_ang, ANG_HI, adj_ang_lo),
                    remap(dip_ang, ANG_HI, adj_ang_lo))
    len_score = remap(len_ratio, LEN_HI, LEN_LO)
    return W_ANG * ang_score + W_LEN * len_score


def _bend_score_thumb(lm) -> float:
    """
    엄지 굽힘 점수 계산 (x좌표 기준)
    엄지는 좌우로 굽혀지므로 y좌표 기반 로직 대신 x좌표 비교 사용
    """
    tip_x   = lm[4].x
    ip_x    = lm[3].x
    mcp_x   = lm[2].x
    wrist_x = lm[0].x
    total_span  = abs(mcp_x - wrist_x) + 1e-6
    bent_amount = (ip_x - tip_x) if wrist_x < mcp_x else (tip_x - ip_x)
    return max(0.0, min(1.0, bent_amount / total_span * 3.0))


def _is_finger_pressed_update(hand_key: tuple, finger_name: str, lm,
                               neighbor_scores: dict = None) -> tuple:
    """
    y좌표 하강 속도 기반 타격 판정 (덕성여대 논문 방식)
    반환: (pressed: bool, locked_note: str | None)
    """
    if hand_key not in _finger_states:
        _finger_states[hand_key] = {
            "y_history":   deque(maxlen=VEL_FRAMES + 1),
            "pressed":     False,
            "press_time":  0.0,
            "needs_reset": False,
            "locked_note": None,
            "velocity":    0.0,
            "tip_history": deque(maxlen=VEL_FRAMES + 1),
        }
    state = _finger_states[hand_key]

    cfg   = FINGER_CONFIG[finger_name]
    tip_i = cfg["tip"]

    coord = lm[tip_i].y
    state["y_history"].append(coord)

    tip_x = lm[tip_i].x
    tip_y = lm[tip_i].y
    state["tip_history"].append((tip_x, tip_y))

    if len(state["y_history"]) >= VEL_FRAMES:
        velocity = (state["y_history"][-1] - state["y_history"][-VEL_FRAMES]) / VEL_FRAMES
    else:
        velocity = 0.0

    now = time.time()

    wrist_coord = lm[0].y
    if hand_key[0] not in _wrist_y_history:
        _wrist_y_history[hand_key[0]] = deque(maxlen=VEL_FRAMES + 1)
    _wrist_y_history[hand_key[0]].append(wrist_coord)

    wrist_hist = _wrist_y_history[hand_key[0]]
    if len(wrist_hist) >= VEL_FRAMES:
        wrist_vel = (wrist_hist[-1] - wrist_hist[-VEL_FRAMES]) / VEL_FRAMES
    else:
        wrist_vel = 0.0

    relative_vel = velocity - wrist_vel * 2.5
    state["velocity"] = relative_vel

    if state["needs_reset"] and finger_name != "thumb":
        if relative_vel <= RELEASE_VEL_TH:
            state["needs_reset"] = False
            state["locked_note"] = None
        return False, None

    if not state["pressed"]:
        if now - state["press_time"] < PRESS_COOLDOWN:
            return False, None
        th = PRESS_VEL_TH * 0.4 if finger_name == "thumb" else PRESS_VEL_TH

        if finger_name == "thumb":
            bend = _bend_score_thumb(lm)
            if bend >= 0.35:
                state["pressed"]    = True
                state["press_time"] = now
        else:
            cfg  = FINGER_CONFIG[finger_name]
            tilt = get_hand_tilt(lm)
            bend = _bend_score_finger_raw(
                lm,
                tip_i=cfg["tip"], dip_i=cfg["dip"],
                pip_i=cfg["pip"], mcp_i=cfg["mcp"],
                tilt_deg=tilt
            )
            if relative_vel >= th and bend >= MIN_BEND_TH:
                state["pressed"]    = True
                state["press_time"] = now
    else:
        if finger_name == "thumb":
            bend = _bend_score_thumb(lm)
            if bend < 0.15:
                state["pressed"]     = False
                state["needs_reset"] = False
                state["locked_note"] = None
        else:
            if relative_vel <= RELEASE_VEL_TH:
                state["pressed"]     = False
                state["needs_reset"] = True
                state["locked_note"] = None

    return state["pressed"], state.get("locked_note")


def _is_fist_landmarks(lm):
    MARGIN = 0.04
    for t in [8, 12, 16, 20]:
        if lm[t].y < lm[t - 2].y + MARGIN:
            return False
    return True


def detect_fist(result) -> int:
    if not (result and result.multi_hand_landmarks):
        return 0
    return sum(1 for hand in result.multi_hand_landmarks
               if _is_fist_landmarks(hand.landmark))


def detect_open_palm(lms):
    tip = [8, 12, 16, 20]
    return sum(1 for t in tip if lms[t].y < lms[t - 2].y) >= 3


def is_index_press(result):
    MARGIN_Y = 0.018
    ANG_HI, ANG_LO = 175.0, 110.0
    LEN_HI, LEN_LO = 0.45, 0.15
    W_ANG, W_LEN = 0.6, 0.4
    _PRESS_TH, _REL_TH = 0.40, 0.12

    if not (result and result.multi_hand_landmarks):
        _press_scores.clear()
        _press_state["pressed"] = False
        return False

    lm = result.multi_hand_landmarks[0].landmark

    def y(i):
        return lm[i].y

    def extended(tip, pip):
        return y(tip) < y(pip) - MARGIN_Y

    ext_cnt = sum(1 for tip, pip in [(12, 10), (16, 14), (20, 18)] if extended(tip, pip))
    palm_open = (ext_cnt >= 2)

    mcp = (int(lm[5].x * shared.WIN_W), int(lm[5].y * shared.WIN_H))
    pip = (int(lm[6].x * shared.WIN_W), int(lm[6].y * shared.WIN_H))
    dip = (int(lm[7].x * shared.WIN_W), int(lm[7].y * shared.WIN_H))
    tip = (int(lm[8].x * shared.WIN_W), int(lm[8].y * shared.WIN_H))

    def _angle(a, b, c):
        ab = (a[0] - b[0], a[1] - b[1])
        cb = (c[0] - b[0], c[1] - b[1])
        lab = math.hypot(*ab)
        lcb = math.hypot(*cb)
        if lab < 1e-6 or lcb < 1e-6:
            return 180.0
        cosv = (ab[0] * cb[0] + ab[1] * cb[1]) / (lab * lcb)
        cosv = max(-1, min(1, cosv))
        return math.degrees(math.acos(cosv))

    pip_ang = _angle(mcp, pip, dip)
    dip_ang = _angle(pip, dip, tip)
    below   = (y(8) > y(6) + MARGIN_Y)

    wrist   = (int(lm[0].x * shared.WIN_W), int(lm[0].y * shared.WIN_H))
    mid_mcp = (int(lm[9].x * shared.WIN_W), int(lm[9].y * shared.WIN_H))
    hand_scale = max(1.0, math.hypot(mid_mcp[0] - wrist[0], mid_mcp[1] - wrist[1]))

    idx_len   = math.hypot(tip[0] - pip[0], tip[1] - pip[1])
    len_ratio = idx_len / hand_scale

    def remap(v, hi, lo):
        if v >= hi: return 0.0
        if v <= lo: return 1.0
        return (hi - v) / (hi - lo)

    ang_score  = max(remap(pip_ang, ANG_HI, ANG_LO), remap(dip_ang, ANG_HI, ANG_LO))
    len_score  = remap(len_ratio, LEN_HI, LEN_LO)
    bend_score = W_ANG * ang_score + W_LEN * len_score

    frame_score = bend_score
    _press_scores.append(frame_score)
    avg_score = sum(_press_scores) / len(_press_scores)

    now_t = time.time()
    if not _press_state["pressed"]:
        if avg_score >= _PRESS_TH:
            _press_state["pressed"]    = True
            _press_state["press_time"] = now_t
    else:
        held = now_t - _press_state.get("press_time", now_t)
        if held > 0.15 and avg_score <= _REL_TH:
            _press_state["pressed"] = False

    try:
        shared.PRESS_DBG["pip"]     = float(pip_ang)
        shared.PRESS_DBG["dip"]     = float(dip_ang)
        shared.PRESS_DBG["lenr"]    = float(len_ratio)
        shared.PRESS_DBG["bend"]    = float(bend_score)
        shared.PRESS_DBG["avg"]     = float(avg_score)
        shared.PRESS_DBG["pressed"] = bool(_press_state["pressed"])
        shared.PRESS_DBG["series"]  = list(_press_scores)
    except Exception:
        pass

    return _press_state["pressed"]


def _dedup_overlapping(tip_notes: list) -> list:
    """
    손가락 겹침 처리:
    두 tip이 OVERLAP_THRESHOLD 픽셀 이내면 y좌표가 더 낮은(더 굽혀진) 것만 유효 처리
    tip_notes: [(tip_x, tip_y, note_str), ...]
    반환: 중복 제거된 note_str 리스트
    """
    used   = [False] * len(tip_notes)
    result = []
    for i, (x1, y1, n1) in enumerate(tip_notes):
        if used[i]:
            continue
        keep = True
        for j, (x2, y2, n2) in enumerate(tip_notes):
            if i == j or used[j]:
                continue
            if math.hypot(x1 - x2, y1 - y2) < OVERLAP_THRESHOLD:
                if y1 < y2:
                    keep = False
                    break
                else:
                    used[j] = True
        if keep:
            result.append(n1)
    return result


def get_all_pressed_notes(result) -> set:
    """
    양손 × 5손가락 → 타격된 건반 set 반환
    locked_note로 드래그 방지 유지
    종료 타이머 작동 중에는 차단
    """
    if _exit_t.get("start") is not None:
        return set()

    if not (result and result.multi_hand_landmarks):
        for state in _finger_states.values():
            state["y_history"].clear()
            state["pressed"]     = False
            state["needs_reset"] = False
            state["locked_note"] = None
        return set()

    tip_notes = []

    for hand_idx, hand_lm in enumerate(result.multi_hand_landmarks):
        lm = hand_lm.landmark

        if result.multi_handedness and hand_idx < len(result.multi_handedness):
            hand_label = result.multi_handedness[hand_idx].classification[0].label.lower()
        else:
            hand_label = f"hand{hand_idx}"

        for finger_name, cfg in FINGER_CONFIG.items():
            hand_key = (hand_label, finger_name)
            pressed, locked_note = _is_finger_pressed_update(hand_key, finger_name, lm)

            if pressed:
                tip_i = cfg["tip"]
                tx = int(lm[tip_i].x * shared.WIN_W)
                ty = int(lm[tip_i].y * shared.WIN_H)

                if locked_note is None:
                    thumb_state = _finger_states.get(hand_key)
                    if finger_name == "thumb" and thumb_state and thumb_state.get("press_xy"):
                        px = int(thumb_state["press_xy"][0] * shared.WIN_W)
                        py = int(thumb_state["press_xy"][1] * shared.WIN_H)
                        note = hit_test_note_strict(px, py)
                    else:
                        note = hit_test_note_strict(tx, ty)
                    if note:
                        _finger_states[hand_key]["locked_note"] = note
                        tip_notes.append((tx, ty, note))
                else:
                    tip_notes.append((tx, ty, locked_note))

    return set(_dedup_overlapping(tip_notes))


def hit_test_note_strict(tx: int, ty: int):
    if not shared._piano_key_boxes:
        # 레이아웃이 아직 초기화 안 됐으면 None 반환
        return None
    for note in shared.PIANO_BLACK_NOTES:
        if shared._piano_key_boxes[note].collidepoint(tx, ty):
            return note
    for note in shared.PIANO_WHITE_NOTES:
        if shared._piano_key_boxes[note].collidepoint(tx, ty):
            return note
    return None
