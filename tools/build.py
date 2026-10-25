# -*- coding: utf-8 -*-
r"""본 빌드 (2026-10-25) — 번역 적재기 결과(work/tr/places.tsv) → GUN.AD2 → 트랙 1

  python tools/build.py [번역 TSV·폴더 …]   적재기(load_tr)부터 다시 돌림(막힌 줄 있으면 멈춤) → work/build/kr/
  python tools/build.py --fake=1.3          가짜 한글로 전 과정 시험

  ① 글꼴(블록 85, 1비트 16×12): 한자 칸(16~47구, 3,008칸) 통째로 한글 자원 — 번역에 쓰인 한글·한글식 부호(, . … ! ? 등)를
     갈무리11 로 그려 차례로 배정(원문 한자 보존 안 함, 전프로젝트 규칙).
  ② 문장: 블록마다 번역문을 블록 끝에 덧붙이고(같은 바이트는 한 번만, 4바이트 정렬, 끝 0x00) «0x10SS xxxx» 참조를 새 위치로.
     places.tsv «*» = 그 문장을 가리키는 모든 참조, 16진 참조 = 그 참조 하나만(사본).
     원래 문장 바이트는 그대로 둠(죽은 자리) → 블록 안 다른 데이터·명령은 한 바이트도 안 바뀜(검산).
  ③ GUN.AD2 = 머리(ad2.build) + 블록을 섹터 단위로 다시 이음. 램: 장면 블록은 0x002A0EB4 에서 끝나게 아래로 쌓이고
     그 밑 0x0025FDD8~ 약 220 KB 가 상태 10개 모두 0 → 블록 하나 커짐 상한 0x8000 으로 막음.
  ④ 트랙 1: GUN.AD2(LBA 99)는 제자리에서 바로 뒤 VOICE_OP.AD2 자리까지 쓸 수 있게 하고, VOICE_OP 은 늘 «파일 영역 끝(LBA 187290)»
     고정 자리로 옮김(빌드마다 같은 LBA). 늘어난 섹터만큼 CDDA1(트랙 2 가리킴)·PVD 볼륨 크기도. 바뀐 섹터만 EDC/ECC 새로."""
import collections, os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import ad2, bdf, cdmode1, gbcode as G, load_tr as L
from iso9660 import Iso

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.environ.get('GUNBLAZE_ROM', r'C:\claude\roms\ss\GunBlaze-S (Japan)')
NAME = 'GunBlaze-S (Japan)'
OUT = os.path.join(ROOT, 'work', 'build', 'kr')
GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
FONT_BLK = 85
CELL0, CELL1 = 15 * 94, 47 * 94                # 16~47구
MAX_GROW = 0x8000
FILES_END, GAP, TRACK = 187290, 150, 187440    # 마지막 파일 VOICE_SW 끝 · 뒷간격 · 트랙 1 섹터 수
GUN_LBA, VOP = 99, '/VOICE_OP.AD2'


# ───────── ① 글꼴 ─────────
# 게임이 글자 코드를 직접 찍는 고정 글자(문자열 아님 — 추출 대상 아님): 원래 한자 칸에 한글을 그대로 그림, 이 칸은 다른 한글에 안 줌
#   弾(0x8CA1) = 화면 위 HUD «弾 ---/---»(2026-10-25 실기 스샷)
FIXED = {0x8CA1: '탄'}


def font_cells(chars):
    need = sorted(c for c in chars if '가' <= c <= '힣') + sorted(c for c in chars if c in L.DRAWN)
    free = [0x8000 + i for i in range(CELL0, CELL1) if 0x8000 + i not in FIXED]
    assert len(need) <= len(free), ('글꼴 칸 모자람', len(need))
    return {c: free[i] for i, c in enumerate(need)}


def draw_font(d, fo, cmap):
    fnt = bdf.Font(GALMURI)
    for ch, code in cmap.items():
        pts, _ = fnt.draw(ch)
        rows = [0] * 12
        for x, y in pts:
            yy, xx = y - 3, x + 1                      # PoC 실기 위치(갈무리11 윗선 3 → 칸 0행, 왼쪽 1칸)
            assert 0 <= yy < 12 and 0 <= xx < 16, ('글자가 칸 밖', ch, x, y)
            rows[yy] |= 0x8000 >> xx
        if not pts: assert ch == ' ', ('갈무리에 없는 글자', ch)
        p = fo + (code - 0x8000) * 24
        d[p:p + 24] = b''.join(r.to_bytes(2, 'big') for r in rows)


# ───────── ② 문장 ─────────
def encode(s, cmap):
    out = bytearray()
    for x in L.items(s):
        if x[0] == 'n': out.append(0x0E)
        elif x[0] == 'w': out.append(0x17)
        elif x[0] == 'x': out += int(x[1], 16).to_bytes(len(x[1]) // 2, 'big')   # {0E}류 1바이트 · {8491} 아이콘 2바이트
        else:
            c = x[1]
            if c in cmap: out += cmap[c].to_bytes(2, 'big')
            else: out += G.enc(c)                    # 원본 글꼴(　「」『』・ 전각 영숫자 등) — 없으면 실패
    out.append(0)
    while len(out) % 4: out.append(0)
    return bytes(out)


def load_places():
    star, one = {}, {}
    for ln in open(os.path.join(ROOT, 'work', 'tr', 'places.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if not ln: continue
        bi, off, ref, n, s = ln.split('\t')
        if ref == '*': star[(int(bi), int(off, 16))] = s
        else: one[(int(bi), int(ref, 16))] = s
    return star, one


def patch_blocks(d, blk, star, one, cmap):
    """→ {블록: 새 바이트}, 참조 바꾼 수"""
    new = {}; nref = 0
    targets = collections.defaultdict(dict)            # 블록 → {옛 위치: 새 위치}
    refvar = {}                                        # (블록, 참조 위치) → 새 위치
    for bi in sorted({k[0] for k in star} | {k[0] for k in one}):
        o, s = blk[bi]; b = bytearray(d[o:o + s]); assert len(b) % 4 == 0
        pool = {}
        def put(bs):
            if bs not in pool: pool[bs] = len(b); b.extend(bs)
            return pool[bs]
        for (bb, off), st in sorted(star.items()):
            if bb == bi: targets[bi][off] = put(encode(st, cmap))
        for (bb, rp), st in sorted(one.items()):
            if bb == bi: refvar[(bi, rp)] = put(encode(st, cmap))
        assert len(b) // 4 < 0x10000, ('블록이 참조 범위(256 KB) 넘음', bi)
        assert len(b) - s <= MAX_GROW, ('블록 %d 이 %d B 커짐 — 램 여유 확인 필요' % (bi, len(b) - s))
        new[bi] = b
    for bi, (o, s) in blk.items():                     # 참조 바꾸기(다른 블록이 가리키는 것 포함)
        if not 2000 <= bi < 2118: continue
        b = new.get(bi) or bytearray(d[o:o + s])
        hit = False
        for k in range(0, s - 3, 4):
            w = struct.unpack_from('>I', b, k)[0]
            if w >> 24 != 0x10: continue
            tb = 2000 + ((w >> 16) & 0xFF); off = (w & 0xFFFF) * 4
            np = refvar.get((bi, k)) if tb == bi else None
            if np is None: np = targets.get(tb, {}).get(off)
            if np is None: continue
            struct.pack_into('>I', b, k, (w & 0xFFFF0000) | (np // 4)); nref += 1; hit = True
        if hit: new[bi] = b
    return new, nref


def check_blocks(d, blk, new, star, one, cmap):
    """검산: ⓐ 원래 크기 안은 참조 낱말 말고 한 바이트도 안 바뀜 ⓑ 참조가 가리키는 새 문장 = places 문장"""
    rev = {}
    for c, v in cmap.items(): rev[v] = c
    def dec(b, p):
        out = []
        while b[p]:
            c = b[p]
            if c >= 0x80:
                v = (c << 8) | b[p + 1]; out.append(rev.get(v) or G.ch(v)); p += 2
            else: out.append({0x0E: '{n}', 0x17: '{w}'}.get(c, '{%02X}' % c)); p += 1
        return ''.join(out)
    for bi, b in new.items():
        o, s = blk[bi]; ob = d[o:o + s]
        for k in range(0, s, 4):
            if b[k:k + 4] != ob[k:k + 4]:
                assert b[k] == 0x10 and ob[k] == 0x10 and b[k + 1] == ob[k + 1], ('참조 아닌 바이트 바뀜', bi, hex(k))
    nchk = 0
    for bi in range(2000, 2118):
        o, s = blk[bi]; b = new.get(bi, d[o:o + s]); ob = d[o:o + s]
        for k in range(0, s - 3, 4):
            w, ow = struct.unpack_from('>I', b, k)[0], struct.unpack_from('>I', ob, k)[0]
            if w == ow or w >> 24 != 0x10: continue
            tb = 2000 + ((w >> 16) & 0xFF); off = (w & 0xFFFF) * 4; ooff = (ow & 0xFFFF) * 4
            want = one.get((bi, k)) if tb == bi and (bi, k) in one else star[(tb, ooff)]
            tbb = new.get(tb) or d[blk[tb][0]:blk[tb][0] + blk[tb][1]]
            got = dec(tbb, off)
            assert got == want, ('문장 다름', bi, hex(k), got, want)
            nchk += 1
    return nchk


# ───────── ④ 트랙 1 ─────────
def bcd(v): return ((v // 10) << 4) | (v % 10)


def sector(lba, data):
    s = bytearray(2352)
    s[0] = 0; s[1:11] = b'\xff' * 10; s[11] = 0
    a = lba + 150
    s[12:16] = bytes([bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75), 1])
    s[16:16 + 2048] = data.ljust(2048, b'\0')
    return bytes(cdmode1.fix(s))


def dir_records(iso):
    """경로 → (디렉터리 섹터, 기록 자리, LBA, 크기)"""
    p = iso.pvd(); rl, rs = iso.root(); out = {}
    def walk(lba, size, pre):
        for k in range((size + 2047) // 2048):
            sd = iso.sector(lba + k); i = 0
            while i < 2048 and sd[i]:
                Ln = sd[i]; nm = sd[i + 33:i + 33 + sd[i + 32]]
                if nm not in (b'\0', b'\1'):
                    n = nm.decode('latin1').split(';')[0]
                    l2, s2 = struct.unpack_from('<I', sd, i + 2)[0], struct.unpack_from('<I', sd, i + 10)[0]
                    if sd[i + 25] & 2: walk(l2, s2, pre + n + '/')
                    else: out[pre + n] = (lba + k, i, l2, s2)
                i += Ln
    walk(rl, rs, '/')
    return out


def write_track(gun, orig_gun):
    src = os.path.join(ROM, NAME + ' (Track 1).bin'); dst = os.path.join(OUT, NAME + ' (Track 1).bin')
    iso = Iso(src); recs = dir_records(iso)
    assert iso.nsec == TRACK
    _, _, glba, gsize = recs['/GUN.AD2']; _, _, vlba, vsize = recs[VOP]
    assert glba == GUN_LBA and vlba == GUN_LBA + (gsize + 2047) // 2048, '배치가 조사와 다름'
    vsec = (vsize + 2047) // 2048
    room = vlba + vsec - GUN_LBA
    nsec = (len(gun) + 2047) // 2048
    assert nsec <= room, ('GUN.AD2 가 VOICE_OP 자리까지 넘음', nsec, room)
    grow = vsec; newsec = TRACK + grow
    with open(src, 'rb') as f, open(dst, 'wb') as o:
        left = FILES_END * 2352
        while left:
            b = f.read(min(left, 1 << 24)); o.write(b); left -= len(b)
        f.seek(vlba * 2352)
        for k in range(vsec):                           # VOICE_OP → 끝 고정 자리(헤더 새로)
            raw = f.read(2352); o.write(sector(FILES_END + k, raw[16:2064]))
        for lba in range(FILES_END + vsec, newsec): o.write(sector(lba, bytes(2048)))
    nw = 0
    with open(dst, 'r+b') as o:
        for k in range(room):                           # GUN.AD2 자리(옛 VOICE_OP 자리 포함) — 바뀐 섹터만
            data = gun[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')
            old = orig_gun[k * 2048:(k + 1) * 2048].ljust(2048, b'\0') if k < (gsize + 2047) // 2048 else None
            if data == old: continue
            o.seek((GUN_LBA + k) * 2352); o.write(sector(GUN_LBA + k, data)); nw += 1
        dirs = {}
        def setrec(name, lba, size):
            dl, di, _, _ = recs[name]
            if dl not in dirs: o.seek(dl * 2352 + 16); dirs[dl] = bytearray(o.read(2048))
            dd = dirs[dl]
            struct.pack_into('<I', dd, di + 2, lba); struct.pack_into('>I', dd, di + 6, lba)
            struct.pack_into('<I', dd, di + 10, size); struct.pack_into('>I', dd, di + 14, size)
        setrec('/GUN.AD2', GUN_LBA, len(gun)); setrec(VOP, FILES_END, vsize)
        _, _, cl, cs = recs['/CDDA1']; setrec('/CDDA1', cl + grow, cs)
        for dl, dd in dirs.items(): o.seek(dl * 2352); o.write(sector(dl, bytes(dd)))
        o.seek(16 * 2352 + 16); p = bytearray(o.read(2048))
        v = struct.unpack_from('<I', p, 80)[0] + grow
        struct.pack_into('<I', p, 80, v); struct.pack_into('>I', p, 84, v)
        o.seek(16 * 2352); o.write(sector(16, bytes(p)))
    for ext in (' (Track 2).bin', '.cue'): shutil.copyfile(os.path.join(ROM, NAME + ext), os.path.join(OUT, NAME + ext))
    # 검산: 새 디스크에서 파일을 이름으로 읽어 비교
    ni = Iso(dst); nr = dir_records(ni)
    assert ni.read(nr['/GUN.AD2'][2], nr['/GUN.AD2'][3]) == gun
    assert ni.read(nr[VOP][2], vsize) == iso.read(vlba, vsize)
    for name, (_, _, l, s) in recs.items():
        if name in ('/GUN.AD2', VOP, '/CDDA1') or l + (s + 2047) // 2048 > TRACK: continue
        assert nr[name][2] == l and ni.read(l, min(s, 0x8000)) == iso.read(l, min(s, 0x8000)), name
    return dst, newsec, nw


def main(argv):
    if not L.main(argv): return False
    d = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()); orig = bytes(d)
    t, hend, _ = ad2.parse(d)
    blk = {i: (o + 0x800, s) for i, (o, s) in t.items()}
    star, one = load_places()
    chars = {c for s in list(star.values()) + list(one.values()) for c in L.TOK.sub('', s)}
    cmap = font_cells(chars)
    fo, fs = blk[FONT_BLK]
    draw_font(d, fo, cmap)
    draw_font(d, fo, {ch: code for code, ch in FIXED.items()})          # 고정 글자(HUD 弾 → 탄)
    new, nref = patch_blocks(d, blk, star, one, cmap)
    nchk = check_blocks(orig, blk, new, star, one, cmap)
    # ③ GUN.AD2 다시 잇기
    first = min(o for o, s in t.values()) // 0x800
    sizes = [(i, len(new[i]) if i in new else s) for i, (o, s) in sorted(t.items())]
    head = ad2.build(sizes, first)
    t2, _, _ = ad2.parse(head + bytes(16))
    # 파일 위치 = 표 위치 + 0x800. 머리(2,656 B)가 블록 0(크기 2, 0x800) 위에 겹침 — 블록 0 은 빈 자리(머리 바이트) 그대로 둠
    base = min(o for o, s in t.values() if o + 0x800 >= 0x1000) + 0x800
    assert len(head) <= base, ('머리가 첫 블록을 덮음', len(head))
    out = bytearray(d[:base]); out[:len(head)] = head; out[len(head):hend] = bytes(max(0, hend - len(head)))
    for i, (o, s) in sorted(t2.items()):
        if o + 0x800 < base: assert t[i] == (o, s); continue
        body = bytes(new[i]) if i in new else bytes(d[blk[i][0]:blk[i][0] + blk[i][1]])
        assert len(out) == o + 0x800, (i, len(out), o)
        out += body + bytes((-len(body)) % 0x800)
    tail = max(o + s for o, s in blk.values())
    out += d[(tail + 0x7FF) // 0x800 * 0x800:]                      # 마지막 블록 뒤(있으면) 그대로
    gun = bytes(out)
    t3, _, _ = ad2.parse(gun)
    for i in t:
        if t[i][0] + 0x800 < base: continue
        o, s = t3[i]; want = new[i] if i in new else d[blk[i][0]:blk[i][0] + blk[i][1]]
        assert gun[o + 0x800:o + 0x800 + s] == bytes(want), ('다시 이은 블록 다름', i)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'GUN.AD2'), 'wb').write(gun)
    grow = max((len(new[i]) - t[i][1] for i in new), default=0)
    big = max((len(new[i]) for i in new if i >= 2016), default=0)
    print('글꼴 칸 %d(한글 %d) · 참조 %d · 문장 검산 %d · 바뀐 블록 %d · 가장 커진 블록 +%d B · 가장 큰 장면 블록 %d B · GUN.AD2 %d → %d B'
          % (len(cmap), sum('가' <= c <= '힣' for c in cmap), nref, nchk, len(new), grow, big, len(orig), len(gun)))
    dst, nsec, nw = write_track(gun, orig)
    print('✅ 트랙 1 %d섹터(+%d) · GUN.AD2 섹터 %d개 새로 → %s' % (nsec, nsec - TRACK, nw, OUT))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(sys.argv[1:]) else 1)
