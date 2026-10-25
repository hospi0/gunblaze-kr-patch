# -*- coding: utf-8 -*-
r"""추출 누락 검사 (2026-10-25) — GUN.AD2 전 블록 + 1ST.BIN 을 게임 글자 코드(0x8000+JIS 순번)로 «모든 바이트 위치»에서 훑어
  가나·한자가 든 글자 줄(2글자 이상, 제어 0x0E·0x17 섞여도 됨)을 찾고, 추출(번역할것 _위치.tsv) 문장 범위 밖에 있는 것만 보고.
  python tools/scan_missing.py → work/trcheck/누락후보.tsv (파일·블록·위치·글자 수·내용) + 블록별 합계"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import ad2, gbcode as G, export_tsv as X

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP = re.compile('[ぁ-んァ-ヶ一-龥々ー]')


def corpus_bigrams():
    bg = set()
    import glob
    for f in glob.glob(os.path.join(ROOT, 'data', '번역할것', '번역할것_*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if not ln: continue
            t = re.sub(r'\{[^{}]*\}', '', ln.split('\t')[1])
            bg.update(t[i:i + 2] for i in range(len(t) - 1))
    return bg


BG = None


def textlike(core):
    """이웃 글자 짝의 70% 이상이 원문 말뭉치에 있는 짝(무작위 데이터는 거의 0)"""
    if len(core) < 2: return False
    pairs = [core[i:i + 2] for i in range(len(core) - 1)]
    return sum(p in BG for p in pairs) >= 0.7 * len(pairs)


def runs(b, base=0):
    """→ [(시작, 끝, 문자열)] — 겹치지 않게 앞에서부터"""
    out = []; p = 0; n = len(b)
    while p < n - 1:
        q = p; s = []
        while q < n - 1:
            c = b[q]
            if c >= 0x80:
                ch = G.ch((c << 8) | b[q + 1])
                if not ch or ch == '□' or ch.startswith('{'): break
                s.append(ch); q += 2
            elif c in (0x0E, 0x17) and s: s.append({0x0E: '{n}', 0x17: '{w}'}[c]); q += 1
            else: break
        txt = ''.join(s)
        core = txt.replace('{n}', '').replace('{w}', '')
        if len(core) >= 2 and len(JP.findall(core)) >= 2 and textlike(core):
            out.append((base + p, base + q, txt)); p = q
        else: p += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    global BG; BG = corpus_bigrams()
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    t, _, _ = ad2.parse(d)
    blk = {i: (o + 0x800, s) for i, (o, s) in t.items()}
    # 추출 범위(파일 위치)
    cov = []
    for ln in open(os.path.join(ROOT, 'data', '번역할것', '_위치.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if not ln: continue
        for x in ln.split('\t')[1].split():
            bi, off = x.split(':'); bi = int(bi); off = int(off, 16)
            o, s = blk[bi]; p = o + off                              # 끝 = 글자 단위로 읽어 0x00(전각 공백 80 00 의 00 은 글자 안)
            while d[p]: p += 2 if d[p] >= 0x80 else 1
            cov.append((o + off, p))
    cov.sort()
    import bisect
    starts = [a for a, b in cov]
    def covered(a, e):
        i = bisect.bisect_right(starts, a) - 1
        return i >= 0 and cov[i][0] <= a and e <= cov[i][1] + 1
    owner = sorted((o, s, i) for i, (o, s) in blk.items())
    def block_of(p):
        for o, s, i in owner:
            if o <= p < o + s: return i
        return None
    rows = []
    for a, e, txt in runs(d):
        if covered(a, e): continue
        bi = block_of(a)
        rows.append(('GUN.AD2', bi, a - blk[bi][0] if bi is not None else a, len(txt), txt))
    exe = open(os.path.join(ROOT, 'work', 'disc', '1ST.BIN'), 'rb').read()
    for a, e, txt in runs(exe):
        rows.append(('1ST.BIN', '', a, len(txt), txt))
    os.makedirs(os.path.join(ROOT, 'work', 'trcheck'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'trcheck', '누락후보.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('파일\t블록\t위치\t길이\t내용\n')
        for r in rows: w.write('%s\t%s\t%X\t%d\t%s\n' % r)
    c = collections.Counter((r[0], r[1]) for r in rows)
    print('누락 후보 %d줄' % len(rows))
    for k, v in sorted(c.items(), key=lambda z: -z[1])[:40]: print('  %s 블록 %s: %d' % (k[0], k[1], v))


if __name__ == '__main__':
    main()
