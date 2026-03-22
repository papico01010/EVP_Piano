import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("assets/emo", exist_ok=True)
os.makedirs("assets/ui", exist_ok=True)

def make_img(path, w, h, color, text=""):
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.text((w//2 - len(text)*7, h//2 - 10), text, fill=(255,255,255))
    img.save(path)
    print(f"생성: {path}")

# 감정 이미지
emos = {"happy":(255,200,0), "sad":(100,100,255), "angry":(255,50,50),
        "neutral":(150,150,150), "surprise":(255,150,0),
        "fear":(150,0,200), "disgust":(0,180,0)}
for name, col in emos.items():
    make_img(f"assets/emo/emo_{name}.png", 200, 200, col, name)

# UI 버튼
btns = ["diff_easy","diff_pro","mode_practice","mode_emotion","yes","no"]
for b in btns:
    make_img(f"assets/ui/{b}_normal.png", 300, 120, (60,60,60), b)
    make_img(f"assets/ui/{b}_active.png", 300, 120, (0,120,255), b)

# 피아노 배경
make_img("assets/basic_piano_st.png", 1280, 720, (240,235,220), "PIANO")

print("완료!")