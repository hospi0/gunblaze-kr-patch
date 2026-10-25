"""이어 흘린 자리(work/tr/joins.tsv) 중 «낱말 한가운데서 갈린 것»(않{n}으니까) 찾기 — Kiwi(utils/kiwi-venv)로
   «앞 끝 낱말 + 뒤 첫 낱말»을 띄운 꼴/붙인 꼴 점수 비교 + 뒤 첫 형태소가 어미·조사·접미사면 붙임 → data/붙여잇기.tsv
   실행: C:/claude/utils/kiwi-venv/Scripts/python tools/join_check.py"""
import os, re
from kiwipiepy import Kiwi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{[^{}]*\}')
k = Kiwi()
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'tr', 'joins.tsv'), encoding='utf-8-sig')][1:]
out = []
for a, b, ta, tb, where in rows:
    pa = TOK.sub('', ta).replace('　', ' ').rstrip()
    pb = TOK.sub('', tb).replace('　', ' ').lstrip()
    if not pa or not pb or not re.match('[가-힣]', pa[-1]) or not re.match('[가-힣]', pb[0]): continue
    wa, wb = pa.split(' ')[-1], pb.split(' ')[0]
    sp = k.analyze(wa + ' ' + wb)[0]; nsp = k.analyze(wa + wb)[0]
    first_b = [t for t in sp[0] if t.start >= len(wa) + 1][:1]
    tag = first_b[0].tag if first_b else ''
    glue = tag.startswith(('E', 'J', 'XS', 'VCP')) or nsp[1] - sp[1] > 8
    out.append((a, b, wa, wb, tag, '%.1f' % (nsp[1] - sp[1]), '붙임' if glue else '', where))
with open(os.path.join(ROOT, 'work', 'tr', 'join_check.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
    w.write('앞\t뒤\t앞 끝말\t뒤 첫말\t뒤 첫 품사\t붙인꼴 점수차\t판정\t위치\n')
    for r in out: w.write('\t'.join(r) + '\n')
with open(os.path.join(ROOT, 'data', '붙여잇기.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
    w.write('앞\t뒤\t앞 끝말\t뒤 첫말\n')
    for r in out:
        if r[6]: w.write('\t'.join(r[:4]) + '\n')
print(len(out), '자리 ·', sum(1 for r in out if r[6]), '붙임 후보')
