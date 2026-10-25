# -*- coding: utf-8 -*-
r"""화자 붙이기·말투 검사 (2026-10-25)
  스크립트 순서(load_tr.script_places)에서 «이름{n}» 만 있는 문장 = 화자 줄 → 다음 화자 줄 전까지 대사의 화자.
  python tools/speakers.py → work/trcheck/화자.tsv (번호·화자·원문·번역) + 화자별 말투(존댓말/반말) 비율·튀는 줄 work/trcheck/말투.tsv"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import export_tsv as X, load_tr as L, termscan as T
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLITE = re.compile(r'(요|니다|니까|세요|십시오|죠|지요|요\?|습니다만)[.!?…~」』,\s]*$')


def speaker_map():
    src, locs = L.load_src()
    at = {l: n for n, ls in locs.items() for l in ls}
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read(); B = X.blocks(d)
    sp = {}; cur = None; last_ch = None
    for ch, bi, off, W, rp in L.script_places(d):
        if ch != last_ch: cur = None; last_ch = ch
        n = at.get((bi, off))
        if n is None: continue
        s = src[n]
        if re.fullmatch(r'[^「『　{}]{1,10}\{n\}', s): cur = s[:-3]; continue
        if cur and (s.startswith(('「', '　')) or '」' in s): sp.setdefault(n, collections.Counter())[cur] += 1
    return {n: c.most_common(1)[0][0] for n, c in sp.items()}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = {r[0]: r for r in T.load_rows(os.path.join(ROOT, 'data', '번역'))}
    sp = speaker_map()
    by = collections.defaultdict(list)
    for n, who in sp.items():
        if n in rows: by[who].append(rows[n])
    with open(os.path.join(ROOT, 'work', 'trcheck', '화자.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t화자\t원문\t번역\n')
        for who, rs in by.items():
            for r in rs: w.write('%s\t%s\t%s\t%s\n' % (r[0], who, r[1], r[2]))
    out = []
    for who, rs in sorted(by.items(), key=lambda z: -len(z[1])):
        ends = []
        for r in rs:
            t = L.TOK.sub('', r[2]).rstrip(' 　」』')
            if not re.search(r'[가-힣]', t) or not re.search(r'[.!?…」]$|[가-힣]$', t): continue
            if not ('」' in r[2] or r[1].rstrip('{w}{n}').endswith(('」', '。', '？', '！'))): continue
            ends.append((bool(POLITE.search(t)), r))
        if len(ends) < 5: continue
        p = sum(e for e, _ in ends); q = len(ends) - p
        major = p >= q
        odd = [r for e, r in ends if e != major]
        out.append((who, len(rs), p, q, odd))
    with open(os.path.join(ROOT, 'work', 'trcheck', '말투.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('화자\t번호\t원문\t번역\t(주 말투와 다른 줄)\n')
        for who, n, p, q, odd in out:
            print('%-10s 줄 %4d · 존댓말 %3d · 반말 %3d · 튀는 줄 %d' % (who, n, p, q, len(odd)))
            for r in odd: w.write('%s\t%s\t%s\t%s\n' % (who, r[0], r[1], r[2]))


if __name__ == '__main__':
    main()
