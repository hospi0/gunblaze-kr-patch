# -*- coding: utf-8 -*-
"""번역할 원문 TSV 뽑기 (2026-10-25).
  스크립트 블록 2000~2117 의 «0x10SS xxxx» 참조가 가리키는 문장(첫 바이트 ≥0x80, 0x00 까지)을 모아 같은 원문은 한 줄로.
  제어: 0x0E → {n}(줄바꿈), 0x17 → {w}(대기 ▼), 그 밖 1바이트 → {XX}. 빈 글꼴 칸(□)이 든 것(= 스크립트 숫자를 잘못 읽은 것)·공백뿐인 것은 뺌.
  창 규칙(PoC 실기): 한 줄 19칸, 19칸 꽉 차면 자동 줄바꿈({n} 없음), {w} 붙는 줄은 18칸까지.
  열: 번호 · 원문 · 번역 · 위치(블록:16진 위치, 첫 곳) · 쓰인 곳 수
  python tools/export_tsv.py → data/번역할것/번역할것_NN.tsv (20 KB 단위, 자투리는 앞 파일에) + data/번역할것/_위치.tsv(번호 → 모든 위치)"""
import collections, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import ad2, gbcode as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', '번역할것')
SPLIT = 20 * 1024


def blocks(d):
    t, _, _ = ad2.parse(d)
    return {i: (o + 0x800, s) for i, (o, s) in t.items() if 2000 <= i < 2118}


def refs(d, blk):
    out = collections.defaultdict(set)
    for i, (o, s) in blk.items():
        for k in range(0, s - 3, 4):
            w = struct.unpack_from('>I', d, o + k)[0]
            if w >> 24 == 0x10 and 2000 + ((w >> 16) & 0xFF) in blk:
                out[2000 + ((w >> 16) & 0xFF)].add((w & 0xFFFF) * 4)
    return out


def read_str(b, p):
    """→ (표시 문자열, 끝 위치) 또는 None"""
    out = []
    while p < len(b):
        c = b[p]
        if c == 0: return ''.join(out), p
        if c >= 0x80:
            ch = G.ch((c << 8) | b[p + 1])
            if ch is None or ch == '□': return None
            out.append(ch); p += 2
        else:
            out.append({0x0E: '{n}', 0x17: '{w}'}.get(c, '{%02X}' % c)); p += 1
    return None


def collect(d):
    blk = blocks(d); res = {}
    for bi, offs in refs(d, blk).items():
        o, s = blk[bi]; b = d[o:o + s]
        for off in sorted(offs):
            if off < 0x20 or off >= s: continue
            if b[off] < 0x80 and not (b[off] in (0x0E, 0x17) and off + 1 < s and b[off + 1] >= 0x80): continue   # 줄바꿈·대기로 시작하는 문장도(«{n}　よし」», 2026-10-25 누락 검사)   # 블록 머리(0x14 «86 17 00 00» = 스크립트 명령을 «駅»으로 오인)
            r = read_str(b, off)
            if r: res[(bi, off)] = r[0]
    return res


def main():
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    res = collect(d)
    by = collections.OrderedDict()
    for key in sorted(res):
        s = res[key]
        if not s.replace('　', '').replace('{n}', '').replace('{w}', ''): continue
        by.setdefault(s, []).append(key)
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith('번역할것_'): os.remove(os.path.join(OUT, f))
    head = '번호\t원문\t번역\t위치\t쓰인 곳\n'
    rows = []
    for n, (s, keys) in enumerate(by.items(), 1):
        rows.append('%05d\t%s\t\t%d:%X\t%d\n' % (n, s, keys[0][0], keys[0][1], len(keys)))
    files, cur, size = [], [], 0
    for r in rows:
        rb = len(r.encode('utf-8'))
        if cur and size + rb > SPLIT: files.append(cur); cur, size = [], 0
        cur.append(r); size += rb
    if cur:
        if files and size < SPLIT // 4: files[-1] += cur        # 자투리는 앞 파일에
        else: files.append(cur)
    for k, rs in enumerate(files, 1):
        with open(os.path.join(OUT, '번역할것_%02d.tsv' % k), 'w', encoding='utf-8-sig', newline='\n') as w:
            w.write(head + ''.join(rs))
    with open(os.path.join(OUT, '_위치.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t위치(블록:16진)\n')
        for n, (s, keys) in enumerate(by.items(), 1):
            w.write('%05d\t%s\n' % (n, ' '.join('%d:%X' % k for k in keys)))
    nch = sum(len(s.replace('{n}', '').replace('{w}', '')) for s in by)
    print('문장 %d곳 → 고유 %d줄 · 글자 %d · 파일 %d개 → %s' % (sum(len(v) for v in by.values()), len(by), nch, len(files), OUT))


if __name__ == '__main__':
    main()
