"""
audio.py - 음성 합성 및 재생 모듈
"""
import time
import numpy as np
import pygame

import shared

# ── 오디오 상수 ───────────────────────────────────────────────────────
SAMPLE_RATE = 44100
VOLUME_MAX  = 0.9

NOTES12_STD = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]
NOTE_SEMITONE = {n: i for i, n in enumerate(NOTES12_STD)}

NOTE_NAME_MAP = {
    "C":  "도",  "Cs": "도#", "D":  "레", "Ds": "레#", "E":  "미",
    "F":  "파",  "Fs": "파#", "G":  "솔", "Gs": "솔#", "A":  "라",
    "As": "라#", "B":  "시",
}

# ── 곡 목록 ───────────────────────────────────────────────────────────
SONGS = {
    "반짝반짝":  ["C4","C4","G4","G4","A4","A4","G4","F4","F4","E4","E4","D4","D4","C4"],
    "생축":      ["C4","C4","D4","C4","F4","E4","C4","C4","D4","C4","G4","F4"],
    "징글벨":    ["E4","E4","E4","E4","E4","E4","E4","G4","C4","D4","E4"],
    "리틀람":    ["E4","D4","C4","D4","E4","E4","E4","D4","D4","D4","E4","G4","G4"],
    "환희":      ["E4","E4","F4","G4","G4","F4","E4","D4","C4","C4","D4","E4","E4","D4","D4"],
    "런던":      ["G4","A4","G4","F4","E4","F4","G4","D4","E4","F4","E4","F4"],
    "프레르":    ["C4","D4","E4","C4","C4","D4","E4","C4","E4","F4","G4","E4","F4","G4"],
    "세인츠":    ["C4","E4","F4","G4","C4","E4","F4","G4","E4","F4","G4","A4","G4","F4","E4","C4"],
    "로우로우로우": ["C4","C4","C4","D4","E4","E4","D4","E4","F4","G4"],
    "양키":      ["C4","C4","D4","E4","C4","E4","D4","C4"],
}


# ── 주파수 계산 ───────────────────────────────────────────────────────
def tone_freq(note12: str, octave: int) -> float:
    midi = 60 + (octave - 4) * 12 + NOTE_SEMITONE[note12]
    return 440.0 * (2 ** ((midi - 69) / 12))


def make_tone(freq: float = 440.0, length: float = 1.0) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * length)
    if n <= 0:
        n = SAMPLE_RATE // 10
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    wave = (
        0.5  * np.sin(2 * np.pi * freq * t) +
        0.3  * np.sin(2 * np.pi * freq * 2 * t) +
        0.15 * np.sin(2 * np.pi * freq * 3 * t) +
        0.05 * np.sin(2 * np.pi * freq * 4 * t)
    ).astype(np.float32)
    r = max(1, int(0.01 * SAMPLE_RATE))
    env = np.ones_like(wave)
    env[:r]  = np.linspace(0, 1, r, dtype=np.float32)
    env[-r:] = np.linspace(1, 0, r, dtype=np.float32)
    wave = wave * env
    wave = wave / np.max(np.abs(wave) + 1e-6) * 0.9
    wave_i16 = (wave * 32767).astype(np.int16)
    stereo = np.column_stack([wave_i16, wave_i16])
    return pygame.sndarray.make_sound(stereo.copy())


def get_sound(note12: str, octave: int) -> pygame.mixer.Sound:
    key = (note12, octave)
    if key not in shared.SND_CACHE:
        shared.SND_CACHE[key] = make_tone(tone_freq(note12, octave))
    return shared.SND_CACHE[key]


# ── 다중 음 동시 관리 매니저 ──────────────────────────────────────────
class MultiNoteManager:
    """
    NoteHoldManager 다중화 버전
    손가락마다 독립 채널 관리 → 코드(화음) 및 양손 연주 지원
    """
    def __init__(self, max_notes: int = 10, decay_time: float = 1.5):
        self.decay_time = decay_time
        self.max_notes  = max_notes
        # note_str → {"channel": ch, "volume": float, "start_t": float}
        self._active: dict = {}

    def reset(self):
        for info in self._active.values():
            if info["channel"]:
                info["channel"].fadeout(100)
        self._active.clear()

    def update(self, pressed_notes: set) -> set:
        """
        pressed_notes: 이번 프레임에 눌린 건반 set
        반환: 현재 재생 중인 건반 set
        """
        now = time.time()

        # 새로 눌린 음 재생
        for note in pressed_notes:
            if note not in self._active:
                if len(self._active) >= self.max_notes:
                    continue
                base12 = note[:-1] if note[-1].isdigit() else note
                octave = int(note[-1]) if note[-1].isdigit() else 4
                ch = pygame.mixer.find_channel(True)
                if ch:
                    snd = get_sound(base12, octave)
                    ch.play(snd, loops=-1)
                    def _ob(o):
                        return {2: 2.0, 3: 1.8, 4: 1.0, 5: 0.85, 6: 0.75}.get(o, 1.0)
                    vol = min(1.0, VOLUME_MAX * _ob(octave))
                    ch.set_volume(vol)
                    self._active[note] = {"channel": ch, "volume": vol, "start_t": now}

        # 뗀 음 페이드아웃
        for note in [n for n in self._active if n not in pressed_notes]:
            info = self._active.pop(note)
            if info["channel"]:
                info["channel"].fadeout(120)

        # 볼륨 decay 적용
        for note, info in list(self._active.items()):
            elapsed = now - info["start_t"]
            vol = max(0.0, 1.0 - elapsed / self.decay_time) * VOLUME_MAX
            info["volume"] = vol
            if info["channel"]:
                info["channel"].set_volume(vol)

        return set(self._active.keys())


class NoteHoldManager:
    def __init__(self, decay_time=1.5, press_frames=3, release_frames=2):
        self.state    = "idle"
        self.channel  = None
        self.volume   = 0.0
        self.start_t  = 0.0
        self.decay_time = max(0.2, decay_time)
        self.note     = None
        self._press_cnt   = 0
        self._release_cnt = 0
        self._need_press_frames   = max(1, press_frames)
        self._need_release_frames = max(1, release_frames)

    def reset(self):
        if self.channel:
            self.channel.fadeout(100)
        self.state    = "idle"
        self.channel  = None
        self.volume   = 0.0
        self.note     = None
        self._press_cnt   = 0
        self._release_cnt = 0

    def update(self, bent, note12, octave):
        if bent:
            self._press_cnt   += 1
            self._release_cnt  = 0
        else:
            self._release_cnt += 1
            self._press_cnt    = 0
        now = time.time()
        if self.state == "idle":
            if (bent and self._press_cnt >= self._need_press_frames
                    and note12 is not None and octave is not None):
                self.note    = (note12, octave)
                self.channel = pygame.mixer.find_channel(True)
                if self.channel:
                    snd = get_sound(note12, octave)
                    self.channel.play(snd, loops=-1)

                    def _octave_boost(oct):
                        boosts = {2: 2.0, 3: 1.8, 4: 1.0, 5: 0.85, 6: 0.75}
                        return boosts.get(oct, 1.0)

                    self.volume = min(1.0, VOLUME_MAX * _octave_boost(octave))
                    self.channel.set_volume(self.volume)
                self.start_t = now
                self.state   = "pressed"
        elif self.state == "pressed":
            if self._release_cnt >= self._need_release_frames:
                if self.channel:
                    self.channel.fadeout(120)
                self.state   = "idle"
                self.channel = None
                self.volume  = 0.0
                self.note    = None
            else:
                elapsed      = now - self.start_t
                remain       = max(0.0, 1.0 - (elapsed / self.decay_time))
                self.volume  = remain * VOLUME_MAX
                if self.channel:
                    self.channel.set_volume(self.volume)
        if self.note is None:
            return None
        return f"{self.note[0]}{self.note[1]}"
