# -*- coding: utf-8 -*-
"""GUN.AD2 머리(블록 표) 읽기·쓰기 (2026-10-25, 1ST.BIN 0x0604E572 해석).
  머리 = «AD20» + 가변 길이 정수들(바이트 하위 7비트, 최상위 비트 1 = 계속, 큰 쪽부터).
  v0 = 첫 블록 섹터. 이후 반복: n = 읽기
     n ≠ 0 → 블록[번호] = (섹터×0x800, n), 섹터 += ceil(n/0x800), 번호 += 1
     n = 0 → 번호 = 읽기; 번호 = 0 이고 다음 바이트도 0 이면 끝(아니면 계속).
  게임은 머리 0x2000 B 를 램 0x06095700 에 읽어 표(0x060B5704, 8 B × 번호)를 만든다.
  python tools/ad2.py      → 원본 머리 해석 + 램 표(스테이트 s4)와 대조"""
import os, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = 0x2000


def _rd(d, p):
    v = 0
    while True:
        b = d[p]; p += 1; v = (v << 7) | (b & 0x7F)
        if not b & 0x80: return v, p


def parse(d):
    """→ {번호: (위치, 크기)}, 머리 끝 위치, 첫 섹터"""
    assert d[:4] == b'AD20'
    p = 4; sec, p = _rd(d, p); idx = 0; out = {}
    while True:
        n, p = _rd(d, p)
        if n:
            out[idx] = (sec * 0x800, n); sec += (n + 0x7FF) // 0x800; idx += 1
            continue
        idx, p = _rd(d, p)
        if idx == 0 and d[p] == 0: return out, p, None


def _wr(v):
    g = [v & 0x7F]; v >>= 7
    while v: g.append(0x80 | (v & 0x7F)); v >>= 7
    return bytes(reversed(g))


def build(blocks, first_sec):
    """blocks = [(번호, 크기)] 번호 오름차순, 섹터는 first_sec 부터 이어 붙임 → 머리 바이트"""
    out = bytearray(b'AD20') + _wr(first_sec); idx = 0
    for i, n in blocks:
        assert n > 0
        if i != idx: out += _wr(0) + _wr(i); idx = i
        out += _wr(n); idx += 1
    out += _wr(0) + _wr(0) + b'\0'
    assert len(out) <= HEAD, len(out)
    return bytes(out)


if __name__ == '__main__':
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    t, end, _ = parse(d)
    print('블록 %d개 · 머리 끝 0x%X · 번호 %d~%d · 끝 위치 0x%X / 파일 0x%X' % (
        len(t), end, min(t), max(t), max(a + b for a, b in t.values()), len(d)))
    m = open(os.path.join(ROOT, 'work', 'mem', 's4', 'WorkRAMH.bin'), 'rb').read()
    bad = 0
    for i in range(5256):
        o, s = struct.unpack_from('>II', m, 0xB5704 + i * 8)
        if t.get(i, (0, 0)) != (o, s): bad += 1
    print('램 표와 다른 칸', bad)
    first = min(t.values())[0] // 0x800
    again = build(sorted((i, s) for i, (o, s) in t.items()), first)
    print('다시 만든 머리 = 원본', again == d[:len(again)], len(again))
