# -*- coding: utf-8 -*-
r"""건블레이즈 — 용어·이름 통일 후보 찾기 (2026-10-25, 린다 큐브 tools/termscan.py 를 옮김)
  python tools/termscan.py [폴더=data/번역]      (열: 번호 · 원문 · 번역 …, 고침은 data/고침.tsv 를 덮어 봄)
  원문 가타카나 낱말(3자 이상)·한자 낱말(2자 이상)이 3줄 이상에 나오면, 그 줄들 번역의 한글 낱말(어절 앞부분) 중
  가장 많이 함께 나오는 것(대표)을 잡고, 대표가 없는 줄에서 대표와 닮은 낱말(첫 글자 같음·편집거리 작음)을 «흔들림»으로 적음.
  → work/trcheck/용어흔들림.tsv (원어 · 대표(줄 수) · 흔들린 꼴:번호)  — 자동 수정 안 함(사람이 고름)
"""
import glob, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
TOK = re.compile(r'\{[^{}]*\}')


def ed(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]


def words(t):
    t = TOK.sub(' ', t)
    ws = set()
    for w in re.findall(r'[가-힣]+', t):
        for n in range(2, min(len(w), 6) + 1):
            ws.add(w[:n])
    return ws


def load_rows(src):
    rows = {}
    for p in sorted(glob.glob(os.path.join(src, '*.tsv'))):
        for ln in open(p, encoding='utf-8-sig').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 3 and c[2]: rows[c[0]] = [c[0], c[1], c[2]]
    fx = os.path.join(ROOT, 'data', '고침.tsv')
    if os.path.exists(fx):
        for ln in open(fx, encoding='utf-8-sig').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 2 and c[0] in rows: rows[c[0]][2] = c[1]
    return list(rows.values())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', '번역')
    rows = load_rows(src)
    occ = collections.defaultdict(list)
    for r in rows:
        o = TOK.sub('＿', r[1])
        for k in set(re.findall(r'[ァ-ヴー・]{3,}', o)) | set(re.findall(r'[一-龥]{2,4}', o)):
            occ[k.strip('・')].append(r)
    out = []
    for k, rs in sorted(occ.items(), key=lambda z: -len(z[1])):
        if len(rs) < 3: continue
        ws = [words(r[2]) for r in rs]
        c = collections.Counter(w for s in ws for w in s)
        if not c: continue
        top = max(c.values())
        cand = [w for w, n in c.items() if n >= top * 0.9]
        rep = max(cand, key=lambda w: (len(w), c[w]))
        if c[rep] < len(rs) * 0.5 or c[rep] == len(rs): continue
        var = collections.defaultdict(list)
        for r, s in zip(rs, ws):
            if rep in s: continue
            sim = [w for w in s if len(w) >= 2 and w[0] == rep[0] and w != rep and ed(w, rep) <= max(1, len(rep) // 3)
                   and not w.startswith(rep) and not rep.startswith(w)]
            var[max(sim, key=len) if sim else '(없음)'].append(r[0])
        out.append((k, '%s(%d/%d)' % (rep, c[rep], len(rs)),
                    ' · '.join('%s:%s' % (v, ','.join(ids[:12])) for v, ids in sorted(var.items(), key=lambda z: -len(z[1])))))
    os.makedirs(os.path.join(ROOT, 'work', 'trcheck'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'trcheck', '용어흔들림.tsv'), 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write('원어\t대표\t흔들림(꼴:번호)\n' + ''.join('\t'.join(x) + '\n' for x in out))
    print('줄 %d · 후보 %d' % (len(rows), len(out)))


if __name__ == '__main__':
    main()
