# -*- coding: utf-8 -*-
"""GunBlaze-S 글자 코드 ↔ 문자 (2026-10-25): 코드 = 0x8000 + (구-1)*94 + (점-1), JIS X 0208(EUC-JP 로 변환).
  ★JIS 9~15구(원래 빈 자리)에 게임이 따로 넣은 글자(추출 누락 검사 tools/scan_missing.py 로 찾음, 글꼴 그림으로 판독):
    제2수준 한자 15자(薔薇 = 薔薇十字団 등) + 얼굴 아이콘 2개(0x8491·0x8492 → 토큰 {8491}·{8492})."""
NGLYPH = 4418
EXTRA = {0x849D: '几', 0x84A9: '拉', 0x84AA: '拗', 0x84AB: '揉', 0x84AC: '攣', 0x84AD: '洒', 0x84AE: '璧', 0x84AF: '痙',
         0x84B0: '睨', 0x84B1: '綺', 0x84B2: '薔', 0x84B3: '薇', 0x84B4: '藉', 0x84B5: '贅', 0x84BC: '箋'}
ICONS = {0x8491, 0x8492, 0x8493, 0x848B, 0x848C, 0x848D, 0x848E}   # 얼굴 아이콘·«HP»«SE» 같은 UI 글자 조각(번역 안 함) — 토큰으로
_REV = {c: v for v, c in EXTRA.items()}


def enc(s):
    out = bytearray()
    for c in s:
        if c in _REV: out += _REV[c].to_bytes(2, 'big'); continue
        e = c.encode('euc_jp'); assert len(e) == 2, c
        out += (0x8000 + (e[0] - 0xA1) * 94 + (e[1] - 0xA1)).to_bytes(2, 'big')
    return bytes(out)


def ch(v):
    if v in EXTRA: return EXTRA[v]
    if v in ICONS: return '{%04X}' % v
    if not (0x8000 <= v < 0x8000 + NGLYPH): return None
    r, c = divmod(v - 0x8000, 94)
    try: return bytes([0xA1 + r, 0xA1 + c]).decode('euc_jp')
    except UnicodeDecodeError: return '□'


def dump(d, a, n):
    out = []
    for o in range(a, a + n, 2):
        v = int.from_bytes(d[o:o + 2], 'big'); c = ch(v)
        out.append(c if c else '<%04X>' % v)
    return ''.join(out)
