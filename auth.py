# auth.py
import json
import hashlib
import os
from datetime import date

USERS_FILE   = "users.json"
RECORDS_FILE = "records.json"

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register(username: str, password: str) -> bool:
    """회원가입. 성공 시 True, 이미 존재하면 False"""
    users = _load(USERS_FILE)
    if username in users:
        return False
    users[username] = {"password": _hash(password)}
    _save(USERS_FILE, users)
    return True

def login(username: str, password: str) -> bool:
    """로그인. 성공 시 True"""
    users = _load(USERS_FILE)
    if username not in users:
        return False
    return users[username]["password"] == _hash(password)

def save_record(username: str, song: str, grade: str, score: int):
    """도전연주 결과 저장. 더 높은 등급만 갱신"""
    GRADE_RANK = {"PERFECT": 5, "GREAT": 4, "GOOD": 3, "BAD": 2, "TRY AGAIN": 1}
    records = _load(RECORDS_FILE)
    if username not in records:
        records[username] = {}
    existing = records[username].get(song)
    if existing is None or GRADE_RANK.get(grade, 0) >= GRADE_RANK.get(existing["grade"], 0):
        records[username][song] = {
            "grade": grade,
            "score": score,
            "date":  str(date.today()),
        }
        _save(RECORDS_FILE, records)

def get_records(username: str) -> dict:
    """유저의 전체 기록 반환"""
    records = _load(RECORDS_FILE)
    return records.get(username, {})
