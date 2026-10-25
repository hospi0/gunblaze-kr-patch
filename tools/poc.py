# -*- coding: utf-8 -*-
r"""PoC (2026-10-25): 장면 블록 2062(마크 방) 대사 5문장 한글 — 스샷 my files/할일 4·5·6.
  ① 글꼴(블록 85, GUN.AD2 0x2800, 1비트 16×12): 대사에 한 번도 안 쓰이는 한자 칸에 갈무리11 한글(열 1~11·행 0~10 = 원본 자리).
  ② 블록 2062: 번역문을 블록 끝에 덧붙이고(4바이트 정렬, 끝 0x00), 원래 문장을 가리키던 «0x103E xxxx» 참조만 새 위치로.
     다른 문장·스크립트는 그대로 → 위치 참조 해석 검증. 커진 크기는 섹터 여유 안(파일 배치 그대로), 머리(ad2.build)에 새 크기.
  ③ GUN.AD2 를 원본 트랙 1 사본에 같은 LBA 로 써서 EDC/ECC 다시 계산.
  python tools/poc.py → work/build/poc/ (Track1·Track2·cue)"""
import os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import ad2, bdf, cdmode1, gbcode as G
from iso9660 import Iso

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = r'C:\claude\roms\ss\GunBlaze-S (Japan)'
NAME = 'GunBlaze-S (Japan)'
OUT = os.path.join(ROOT, 'work', 'build', 'poc')
GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
SCENE = 2062
TR = {   # 블록 안 위치 → 번역(제어: \x0E 줄바꿈, \x17 대기). 원문 끝 제어 그대로
    0x5A90: '구웅구웅구웅구웅・・・\x17\x0E',
    0x5A64: '「・・・또야。오늘도 이 소리인가。\x17\x0E',     # 18칸 + ▼(창 19칸 — 19칸이면 ▼가 다음 줄로 밀림, 실기)
    0x5A3C: '　나 참、이 고대 짐승의 포효 같은',       # 19칸 꽉 참 → 원문처럼 자동 줄바꿈(줄바꿈 코드 넣으면 빈 줄)
    0x5A28: '　소리는 대체 어디서\x0E',            # 원문 끝 0x0E(빠뜨렸던 것)
    0x5A0C: '　들려오는 걸까？」\x17\x0E',
}


def enc_text(s, cmap):
    out = bytearray()
    for c in s:
        if c in '\x0E\x17': out.append(ord(c)); continue
        if c == ' ': c = '　'
        if c in cmap: out += cmap[c].to_bytes(2, 'big'); continue
        out += G.enc(c)                                  # 원래 글꼴 글자(부호·가나) — 없으면 enc 가 실패
    out.append(0)
    while len(out) % 4: out.append(0)
    return bytes(out)


def main():
    d = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read())
    t, hend, _ = ad2.parse(d)
    blk = {i: (o + 0x800, s) for i, (o, s) in t.items()}
    # ① 글꼴 칸: 스크립트 블록 대사에 안 나오는 한자 칸(16구~)
    used = set()
    for i in range(2000, 2118):
        o, s = blk[i]; b = d[o:o + s]
        for k in range(0, s - 1):
            if b[k] >= 0x80: used.add((b[k] << 8) | b[k + 1])
    hangul = sorted({c for v in TR.values() for c in v if '가' <= c <= '힣'})
    free = [0x8000 + i for i in range(15 * 94, 47 * 94) if (0x8000 + i) not in used]
    assert len(free) >= len(hangul)
    cmap = dict(zip(hangul, free))
    fnt = bdf.Font(GALMURI); fo, fs = blk[85]
    for ch, code in cmap.items():
        pts, _ = fnt.draw(ch)
        rows = [0] * 12
        for x, y in pts:
            yy, xx = y - 3, x + 1
            assert 0 <= yy < 12 and 0 <= xx < 16, (ch, x, y)
            rows[yy] |= 0x8000 >> xx
        g = b''.join(r.to_bytes(2, 'big') for r in rows)
        d[fo + (code - 0x8000) * 24: fo + (code - 0x8000) * 24 + 24] = g
    # ② 블록 2062: 끝에 덧붙이고 참조 바꾸기
    so, ss = blk[SCENE]
    b = bytearray(d[so:so + ss]); assert len(b) % 4 == 0
    newpos = {}
    for old, s in TR.items():
        newpos[old] = len(b); b += enc_text(s, cmap)
    nref = 0
    for i in range(2000, 2118):
        o, s = blk[i]
        bb = b if i == SCENE else d[o:o + s]
        for k in range(0, len(bb) - 3, 4):
            w = struct.unpack_from('>I', bb, k)[0]
            if w >> 16 == 0x1000 | (SCENE - 2000) and (w & 0xFFFF) * 4 in newpos:
                assert i == SCENE, '다른 블록 참조 %d' % i
                struct.pack_into('>I', bb, k, (w & 0xFFFF0000) | (newpos[(w & 0xFFFF) * 4] // 4)); nref += 1
    assert nref >= len(TR), nref
    nxt = min(o for i, (o, s) in blk.items() if o > so)
    assert so + len(b) <= nxt, ('섹터 여유 넘음', len(b) - ss, nxt - so - ss)
    d[so:so + len(b)] = b
    # 머리: 2062 크기만 바꿈(섹터 배치 그대로)
    sizes = sorted((i, s) for i, (o, s) in t.items()); sizes = [(i, len(b) if i == SCENE else s) for i, s in sizes]
    first = min(o for o, s in t.values()) // 0x800
    head = ad2.build(sizes, first)
    t2, _, _ = ad2.parse(head + bytes(16))
    assert all(t2[i][0] == t[i][0] for i in t), '섹터 배치 바뀜'
    d[:len(head)] = head; d[len(head):hend] = bytes(hend - len(head)) if hend > len(head) else b''
    assert len(d) == os.path.getsize(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'))
    # ③ 트랙 1
    os.makedirs(OUT, exist_ok=True)
    src = os.path.join(ROM, NAME + ' (Track 1).bin'); dst = os.path.join(OUT, NAME + ' (Track 1).bin')
    shutil.copyfile(src, dst)
    for ext in (' (Track 2).bin', '.cue'): shutil.copyfile(os.path.join(ROM, NAME + ext), os.path.join(OUT, NAME + ext))
    iso = Iso(src); ent = [e for e in iso.walk() if e[0] == '/GUN.AD2'][0]; lba = ent[1]
    orig = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    nsec = 0
    with open(dst, 'r+b') as f:
        for k in range(0, len(d), 2048):
            if d[k:k + 2048] == orig[k:k + 2048]: continue
            f.seek((lba + k // 2048) * 2352); sec = bytearray(f.read(2352))
            sec[16:16 + 2048] = d[k:k + 2048].ljust(2048, b'\0'); cdmode1.fix(sec)
            f.seek((lba + k // 2048) * 2352); f.write(sec); nsec += 1
    print('한글 %d자 → 칸 %s… · 문장 %d · 참조 %d · 블록 2062 %d→%d B · 바뀐 섹터 %d → %s' % (
        len(cmap), ','.join('%04X' % v for v in list(cmap.values())[:3]), len(TR), nref, ss, len(b), nsec, OUT))


if __name__ == '__main__':
    main()
