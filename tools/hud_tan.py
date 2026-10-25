"""HUD «弾 ---/---» 한글화: HUD 는 본문 글꼴의 반쪽 칸 두 개(0x848D 왼쪽 · 0x848E 오른쪽, 16×12 1비트)를 5px 간격으로 이어 찍음
   (2026-10-25 스테이트 VDP1 명령표: x=51·56 y=24, «HP» = 0x848B·0x848C). 원본 HUD 꼴(1px 획·10행) 그대로 손으로 그린 «탄».
   python tools/hud_tan.py  → work/preview/hud_tan_preview.png (원본|새것, 실제 색)"""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 9×10 — 왼쪽 반쪽 = 열 0~4(칸 열 2~6), 오른쪽 반쪽 = 열 5~8(칸 열 2~5)
TAN = ['####..#..',
       '#.....#..',
       '####..##.',
       '#.....#..',
       '####..#..',
       '.........',
       '.#.......',
       '.#.......',
       '.#.......',
       '.#######.']
CODES = (0x848D, 0x848E)


def halves():
    """→ {코드: 24바이트}"""
    L = [0] * 12; R = [0] * 12
    for y, row in enumerate(TAN):
        for x, c in enumerate(row):
            if c != '#': continue
            if x < 5: L[y] |= 0x8000 >> (2 + x)
            else: R[y] |= 0x8000 >> (2 + x - 5)
    pack = lambda rs: b''.join(r.to_bytes(2, 'big') for r in rs)
    return {CODES[0]: pack(L), CODES[1]: pack(R)}


def patch(d, fo):
    for code, b in halves().items():
        p = fo + (code - 0x8000) * 24; d[p:p + 24] = b


if __name__ == '__main__':
    from PIL import Image
    fo = 0x2800
    g = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    bg = (84, 80, 44)                                   # 실기 스샷 HUD 바탕 · 글자 색(무기 없음 = 회색 120, 있음 = HP 처럼 흰색)
    new = halves()
    im = Image.new('RGB', (60, 28), bg)
    for row, col in enumerate(((120, 120, 120), (248, 248, 248))):
        for k, src in enumerate((lambda c: g[fo + (c - 0x8000) * 24: fo + (c - 0x8000) * 24 + 24], lambda c: new[c])):
            for j, code in enumerate(CODES):
                b = src(code)
                for y in range(12):
                    r = int.from_bytes(b[y * 2:y * 2 + 2], 'big')
                    for x in range(16):
                        if r & (0x8000 >> x) and x < 8: im.putpixel((2 + k * 30 + x + 5 * j, 1 + row * 14 + y), col)
    out = os.path.join(ROOT, 'work', 'preview', 'hud_tan_preview.png')
    im.resize((im.width * 12, im.height * 12), Image.NEAREST).save(out); print(out)
