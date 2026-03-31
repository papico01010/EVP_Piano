from PIL import Image, ImageDraw
import os

os.makedirs("assets", exist_ok=True)

W, H = 1280, 720
WHITE_NOTES = ["C","D","E","F","G","A","B"]
BLACK_NOTES = ["Cs","Ds","Fs","Gs","As"]
BLACK_POS   = [0, 1, 3, 4, 5]
ALL_NOTES   = ["C","Cs","D","Ds","E","F","Fs","G","Gs","A","As","B"]

def draw_piano_base(w, h):
    """2옥타브(14흰건반) 피아노 배경 이미지 생성."""
    img = Image.new("RGB", (w, h), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    top = int(0.08 * h)
    wh = int(0.78 * h)
    bh = int(0.48 * h)
    ww = w / 14.0  # 14 흰건반
    bw = ww * 0.60
    for i in range(14):
        x = int(i * ww)
        draw.rectangle([x+2, top, x+int(ww)-2, top+wh], fill=(255,255,255), outline=(0,0,0))
    for oct_offset in [0, 7]:
        for i_white in BLACK_POS:
            cx = (oct_offset + i_white + 1.0) * ww
            x = int(cx - bw/2)
            draw.rectangle([x, top, x+int(bw), top+bh], fill=(20,20,20), outline=(0,0,0))
    return img

def draw_key_highlight(w, h, note_with_oct, color_white, color_black):
    """2옥타브 피아노에서 특정 건반 하이라이트. note_with_oct: 'C4', 'Cs5' 등."""
    img = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    top = int(0.08 * h)
    wh  = int(0.78 * h)
    bh  = int(0.48 * h)
    ww  = w / 14.0
    bw  = ww * 0.60

    # 음이름과 옥타브 분리
    if note_with_oct[-1].isdigit():
        note   = note_with_oct[:-1]
        octave = int(note_with_oct[-1])
    else:
        note   = note_with_oct
        octave = 4
    oct_offset = 0 if octave == 4 else 7

    HAS_BLACK_LEFT  = {"D", "E", "G", "A", "B"}
    HAS_BLACK_RIGHT = {"C", "D", "F", "G", "A"}

    if note in BLACK_NOTES:
        i_white = BLACK_POS[BLACK_NOTES.index(note)]
        cx = (oct_offset + i_white + 1.0) * ww
        x  = int(cx - bw / 2)
        draw.rectangle([x, top, x+int(bw), top+bh], fill=color_black, outline=(0,0,0))
    else:
        i  = WHITE_NOTES.index(note)
        li = oct_offset + i  # 14건반 기준 인덱스
        x0 = int(li * ww) + 2
        x1 = int((li + 1) * ww) - 2
        if note in HAS_BLACK_LEFT:
            x0 = int(li * ww + bw / 2) + 1
        if note in HAS_BLACK_RIGHT:
            x1 = int((li + 1) * ww - bw / 2) - 1
        draw.rectangle([x0, top + bh, x1, top + wh], fill=color_white, outline=(0,0,0))
        draw.rectangle([x0, top, x1, top + bh], fill=color_white)
    return img

# 피아노 배경
base = draw_piano_base(W, H)
base.save("assets/basic_piano_st.png")
print("생성: assets/basic_piano_st.png")

# 건반 오버레이 - 옥타브별로 저장 (C4, Cs4, D4 ... C5, Cs5, D5 ...)
for note in ALL_NOTES:
    for octave in [4, 5]:
        note_oct = f"{note}{octave}"
        img_user = draw_key_highlight(W, H, note_oct, (100,180,255,200), (0,100,220,200))
        img_user.save(f"assets/user_push_{note_oct}.png")
        print(f"생성: assets/user_push_{note_oct}.png")
        img_prog = draw_key_highlight(W, H, note_oct, (100,255,150,200), (0,180,80,200))
        img_prog.save(f"assets/program_push_{note_oct}.png")
        print(f"생성: assets/program_push_{note_oct}.png")

# 48키 배경 생성
def draw_piano_base_48(w, h):
    img = Image.new("RGB", (w, h), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    
    cfg_top_margin    = int(0.04 * h)
    cfg_bottom_margin = int(0.04 * h)
    cfg_row_gap       = int(0.02 * h)
    usable_h = h - cfg_top_margin - cfg_bottom_margin - cfg_row_gap
    row_h    = usable_h // 2
    row_top_y = cfg_top_margin
    row_bot_y = cfg_top_margin + row_h + cfg_row_gap

    left  = int(0.012 * w)
    right = int(0.012 * w)
    usable_w = w - left - right
    oct_w = usable_w / 2.0
    white_w = oct_w / 7.0
    black_w = white_w * 0.62
    white_h = int(row_h * 0.95)
    black_h = int(row_h * 0.62)

    for row_y in [row_top_y, row_bot_y]:
        for oct in range(2):
            base_x = left + oct * oct_w
            for i in range(7):
                x = int(base_x + i * white_w)
                draw.rectangle([x+1, row_y, x+int(white_w)-1, row_y+white_h],
                               fill=(255,255,255), outline=(0,0,0))
            for i_white in [0,1,3,4,5]:
                cx = base_x + (i_white + 1.0) * white_w
                x = int(cx - black_w/2)
                draw.rectangle([x, row_y, x+int(black_w), row_y+black_h],
                               fill=(20,20,20), outline=(0,0,0))
    return img

base48 = draw_piano_base_48(W, H)
base48.save("assets/ex_piano_basic_st.png")
print("생성: assets/ex_piano_basic_st.png")

print("완료!")