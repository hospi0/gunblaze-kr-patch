"""창 흉내 미리보기: work/tr/places.tsv 최종 문자열을 스크립트 순서(사슬)대로 이어 찍음 — 실기 스샷과 줄 모양 대조용
   python tools/render_chain.py 2063:6D58 [...]   (블록:위치 가 든 사슬 전체, ▼ 는 ▼, 빈칸은 _)"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import load_tr as L

ROOT = L.ROOT
d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
fin = {}
for l in open(os.path.join(ROOT, 'work', 'tr', 'places.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
    c = l.split('\t')
    if len(c) >= 5: fin[(int(c[0]), c[1].upper(), c[2])] = c[4]
places = L.script_places(d); BLK = L.X.blocks(d)


def text(bi, off, rp):
    k = (bi, '%X' % off)
    v = fin.get(k + ('%X' % rp,)) or fin.get(k + ('*',))
    return v if v is not None else L.X.read_str(d[BLK[bi][0]:BLK[bi][0] + BLK[bi][1]], off)[0]


def render(ch):
    pl = [p for p in places if p[0] == ch and p[3]]
    W = pl[0][3]; lines = ['']
    for _, bi, off, _, rp in pl:
        for it in L.items(text(bi, off, rp)):
            if it[0] == 'n': lines.append(''); continue
            c = L.cells(it)
            if c and len(lines[-1]) >= W: lines.append('')
            if it[0] == 'w': lines[-1] += '▼'; lines.append('---'); lines.append(''); continue
            if c: lines[-1] += '_' if it[1] == L.SPACE else (it[1] if it[0] == 'c' else '◆')
    print('[사슬 %d · 창 %d칸]' % (ch, W))
    for x in lines: print('  |' + x)


for a in sys.argv[1:]:
    bi, off = a.split(':'); bi = int(bi); off = int(off, 16)
    for ch in sorted({p[0] for p in places if p[1] == bi and p[2] == off}): render(ch)
