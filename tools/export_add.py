# -*- coding: utf-8 -*-
"""추출 보충 (2026-10-25) — 번호를 바꾸지 않고 «빠졌던 문장»만 뒤 번호로 덧붙임.
  처음 추출(export_tsv)은 글꼴 표 밖 글자(JIS 9~15구에 게임이 넣은 薔·薇·綺 등, gbcode.EXTRA)가 든 문장을 통째로 버렸다.
  python tools/export_add.py → data/번역할것/번역할것_추가NN.tsv + _위치.tsv 끝에 덧붙임 · 기존 줄 위치가 그대로인지 검산"""
import collections, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import export_tsv as X, load_tr as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', '번역할것')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src, locs = L.load_src()
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    res = X.collect(d)
    by = collections.OrderedDict()
    for key in sorted(res):
        s = res[key]
        if not s.replace('　', '').replace('{n}', '').replace('{w}', ''): continue
        by.setdefault(s, []).append(key)
    have = {s: n for n, s in src.items()}
    for s, n in have.items():                                            # 검산: 기존 줄 위치 그대로
        assert sorted(by.get(s, [])) == sorted(locs[n]), ('기존 줄 위치 달라짐', n, s)
    new = [(s, keys) for s, keys in by.items() if s not in have]
    if not new: print('빠진 문장 없음'); return
    start = max(int(n) for n in src) + 1
    k = 1 + sum(1 for f in os.listdir(OUT) if f.startswith('번역할것_추가'))
    with open(os.path.join(OUT, '번역할것_추가%02d.tsv' % k), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t원문\t번역\t위치\t쓰인 곳\n')
        for i, (s, keys) in enumerate(new):
            w.write('%05d\t%s\t\t%d:%X\t%d\n' % (start + i, s, keys[0][0], keys[0][1], len(keys)))
    with open(os.path.join(OUT, '_위치.tsv'), 'a', encoding='utf-8', newline='\n') as w:
        for i, (s, keys) in enumerate(new):
            w.write('%05d\t%s\n' % (start + i, ' '.join('%d:%X' % kk for kk in keys)))
    print('빠졌던 문장 %d줄(%05d~) · 글자 %d → 번역할것_추가%02d.tsv'
          % (len(new), start, sum(len(L.TOK.sub('', s)) for s, _ in new), k))


if __name__ == '__main__':
    main()
