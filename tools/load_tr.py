# -*- coding: utf-8 -*-
r"""번역 적재기 (2026-10-25) — 번역 TSV → 검사 → 조판 → work/tr/places.tsv(참조 위치마다 최종 문자열)

  python tools/load_tr.py [번역 TSV·폴더 …]      기본 data/번역/ (열: 번호 · 원문 · 번역 …, 번역할것_NN.tsv 와 같은 꼴)
  python tools/load_tr.py --fake                 가짜 한글(원문 글자 수만큼)로 전 과정 시험

  ■ 쓰는 순간 막는 것(하나라도 있으면 places.tsv 를 안 씀)
    · 원문 칸이 번역할것 원문과 다름(줄 어긋남) · 같은 번호 번역이 둘
    · 토큰: {w}(▼) 개수 다름, {XX} 제어 코드 개수 다름, 「」『』 원문보다 적음('…' "…" 는 자동으로 「」『』 복원), 모르는 {…}
    · 실개행·탭 · 가나·한자 남음 · 글꼴에 없는 글자
    · 조판: 한 낱말이 창 한 줄보다 김(글자 단위로 자르지 않음) · 한 쪽(▼ 사이)이 4줄 넘고 원문보다 많음
  ■ 자동으로 하는 것
    · 문장부호 한글식: 、→,  。→.  ・・・/‥/...→…  ！？：；～（）→ !?:;~()   (・ 하나는 그대로 — 이름 사이 점)
    · 부호 뒤 공백 1칸 삭제(전프로젝트 규칙) · 반각 영숫자 → 전각(원본 글꼴)
    · 줄 나누기: 창 폭(얼굴 창 19칸·넓은 창 25칸·설명 24칸, ▼ 도 한 칸)에 맞춰 띄어쓰기·부호 뒤에서 {n}.
      「」 안 둘째 줄부터 «　» 들여쓰기(원문 꼴) · 원문 문장이 줄 끝에서 끝났으면 번역도 줄 끝에서 끝냄.
  ■ 경고만: 이름·메뉴(설명 아닌 2006·2014 한 줄)가 원문보다 김 — 칸이 고정일 수 있어 실기 확인"""
import collections, glob, math, os, re, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import export_tsv as X, gbcode as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', '번역할것')
TRDIR = os.path.join(ROOT, 'data', '번역')
OUT = os.path.join(ROOT, 'work', 'tr')
W_FACE, W_WIDE, W_SYS = 19, 24, 24          # 넓은 창 24칸(2026-10-25 실기 «아름다/운소녀»: 글자 24칸에서 넘어감)
PAGE = 4
# 문장부호 전부(메모리 feedback_no_space_after_punct 와 같은 목록)
PUNCT = (",.!?:;)]}'\"~"
         "、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥")
PMAP = {'、': ',', '。': '.', '，': ',', '．': '.', '！': '!', '？': '?', '：': ':', '；': ';',
        '·': '・', '•': '・', '～': '~', '〜': '~', '（': '(', '）': ')', '‥': '…', '”': '"', '“': '"', '’': "'", '‘': "'"}
DRAWN = set(',.…!?:;~()\'"-%+/&')        # 갈무리에서 그려 넣을 한글식 부호(빌드 때 글꼴 칸 배정)
SPACE = '　'
OPEN, CLOSE = '「『', '」』'
TOK = re.compile(r'\{([^{}]*)\}')


def banner():
    print('━' * 60)
    print(__doc__.split('■', 1)[1].rstrip())
    print('━' * 60)


# ───────── 글자 정리·검사 ─────────
def restore_brackets(src, tr):
    """원문 『』「」 를 번역이 '…' / "…" 로 바꿔 놓았으면 원래 괄호로(falcom ystrans 와 같음)"""
    for (o, c), q in ((('『', '』'), "'"), (('「', '」'), '"')):
        need = src.count(o) - tr.count(o)
        while need > 0:
            m = re.search(re.escape(q) + '([^' + re.escape(q) + ']+?)' + re.escape(q), tr)
            if not m: break
            tr = tr[:m.start()] + o + m.group(1) + c + tr[m.end():]; need -= 1
        # 문장이 여러 줄(참조)로 나뉘어 짝 없는 따옴표 하나만 남은 경우: 여는 쪽은 첫 따옴표, 닫는 쪽은 마지막 따옴표
        if src.count(o) > tr.count(o) and q in tr: i = tr.index(q); tr = tr[:i] + o + tr[i + 1:]
        if src.count(c) > tr.count(c) and q in tr: i = tr.rindex(q); tr = tr[:i] + c + tr[i + 1:]
        # 원문이 닫는 괄호로 끝나는데 번역이 빠뜨림(«…だわ」{w}» → «…잤어.{w}»): 끝 토큰 앞에 되살림(바로 앞 마침표는 원문처럼 뺌)
        ms, mt = re.search(r'((?:\{[^{}]*\})*)$', src), re.search(r'((?:\{[^{}]*\})*)$', tr)
        if src.count(c) - tr.count(c) == 1 and src[:ms.start()].rstrip(SPACE).endswith(c) and not tr[:mt.start()].rstrip(SPACE + ' ').endswith(c):
            body = tr[:mt.start()].rstrip(SPACE + ' ')
            if body.endswith(('.', '。')) and not body.endswith(('..', '。。')): body = body[:-1]
            tr = body + c + tr[mt.start():]
    return tr


def norm(tr):
    """토큰 밖 글자만 바꿈"""
    parts = re.split(r'(\{[^{}]*\})', tr)
    for i in range(0, len(parts), 2):
        t = parts[i]
        t = re.sub(r'・{2,}|\.{2,}', lambda m: '…' * max(1, math.ceil(len(m.group()) / 3)), t)
        t = ''.join(PMAP.get(c, c) for c in t)
        t = ''.join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalnum() else c for c in t)   # 반각 영숫자 → 전각(원본 글꼴)
        parts[i] = t.replace(' ', SPACE)
    tr = ''.join(parts)
    tr = re.sub(SPACE + r'+(?=\{n\}|\{w\}|$)', '', tr)                # 줄 끝 공백(번역자 실수) — 원문 꼴 공백은 check 에서 되살림
    parts = re.split(r'(\{[^{}]*\})', tr)                           # 부호 뒤 공백 1칸 삭제 — 토큰 끝 «}» 는 부호 아님
    for i in range(0, len(parts), 2):
        parts[i] = re.sub('([' + re.escape(PUNCT) + '])' + SPACE + '(?!' + SPACE + ')', r'\1', parts[i])
    return ''.join(parts)


def glyph_ok(c):
    if '가' <= c <= '힣' or c in DRAWN or c == SPACE: return True
    if re.match('[ぁ-んァ-ヶ一-龥々〆]', c): return False
    try: e = c.encode('euc_jp')
    except UnicodeEncodeError: return False
    return len(e) == 2 and 0xA1 <= e[0] < 0xA1 + 8              # 원본 글꼴 1~8구(부호·영숫자·괄호)


def check(src, tr):
    """→ (정리된 번역, 막을 것[], 경고[])"""
    bad = []
    if '\n' in tr or '\r' in tr or '\t' in tr: bad.append('실개행·탭')
    tr = norm(restore_brackets(src, tr))
    m = re.search('(' + SPACE + r'+)((?:\{[^{}]*\})*)$', src)          # 원문 끝 공백(«…ですな」　{w}{n}» 같은 칸 맞춤)은 그대로
    if m and not re.search(SPACE + r'(?:\{[^{}]*\})*$', tr):
        k = len(tr) - len(re.search(r'((?:\{[^{}]*\})*)$', tr).group(1)); tr = tr[:k] + m.group(1) + tr[k:]
    for t in TOK.findall(tr):
        if not (t in ('n', 'w') or re.fullmatch('[0-9A-F]{2}|8[0-9A-F]{3}', t)): bad.append('모르는 토큰 {%s}' % t)
    cs = collections.Counter(t for t in TOK.findall(src) if t != 'n')
    ct = collections.Counter(t for t in TOK.findall(tr) if t != 'n')
    for k in set(cs) | set(ct):
        if cs[k] != ct[k]: bad.append('{%s} 원문 %d개 ≠ 번역 %d개' % (k, cs[k], ct[k]))
    for ch in OPEN + CLOSE:
        if tr.count(ch) < src.count(ch): bad.append('괄호 %s 원문 %d > 번역 %d' % (ch, src.count(ch), tr.count(ch)))
    plain = TOK.sub('', tr)
    jp = sorted({c for c in plain if re.match('[ぁ-んァ-ヶ一-龥々〆]', c)})
    if jp: bad.append('가나·한자 남음 ' + ''.join(jp))
    no = sorted({c for c in plain if not glyph_ok(c) and c not in jp})
    if no: bad.append('글꼴에 없는 글자 ' + ' '.join('%s(U+%04X)' % (c, ord(c)) for c in no))
    return tr, bad, []


# ───────── 조판 ─────────
def items(s):
    """문자열 → [(종류, 값)]: ('c', 글자) · ('n',) · ('w',) · ('x', 'XX')"""
    out = []; p = 0
    for m in TOK.finditer(s):
        out += [('c', c) for c in s[p:m.start()]]
        t = m.group(1); out.append(('n',) if t == 'n' else ('w',) if t == 'w' else ('x', t)); p = m.end()
    return out + [('c', c) for c in s[p:]]


def unitems(it):
    return ''.join(x[1] if x[0] == 'c' else '{n}' if x[0] == 'n' else '{w}' if x[0] == 'w' else '{%s}' % x[1] for x in it)


def cells(x):
    return 1 if x[0] in ('c', 'w') or (x[0] == 'x' and len(x[1]) == 4) else 0   # {8491} 같은 아이콘 = 글자 한 칸


class Cursor:
    """창 흉내: 열·쪽 줄 수·괄호 — 자동 줄바꿈은 «다음 칸을 놓을 때» (19칸 꽉 + {n} 은 원문 261곳 정상)"""
    def __init__(self, W):
        self.W = W; self.col = 0; self.lines = 1; self.quote = 0; self.maxpage = 0

    def put(self, x):
        if x[0] == 'n':
            self.col = 0; self.lines += 1; return
        if cells(x):
            if self.col >= self.W: self.col = 0; self.lines += 1
            self.col += 1
            if x[0] == 'c':
                if x[1] in OPEN: self.quote += 1
                elif x[1] in CLOSE: self.quote = max(0, self.quote - 1)
            if x[0] == 'w':
                self.maxpage = max(self.maxpage, self.lines); self.lines = 0   # ▼ 뒤 다음 줄부터 새 쪽
        if x[0] == 'n' and self.lines == 0: pass

    def feed(self, it):
        for x in it: self.put(x)


def orig_ends_line(src_it, W, col0):
    """원문 문장이 줄 끝에서 끝나는가({n} 로 끝나거나 마지막 줄이 꽉 참)"""
    if src_it and src_it[-1][0] == 'n': return True
    cu = Cursor(W); cu.col = col0; cu.feed(src_it)
    return cu.col >= W


def layout(tr, src, W, col0, quote0, ocol0=0, pl0=1, join_next=False, wsp=0, soft_in=False, next_cont=False, join_sp=True):
    """번역 한 문장을 창 폭 W 에 맞춰 {n} 넣기 → (항목[], 막을 것[], 끝 쪽 줄 수)
       쪽(▼ 사이)이 PAGE 줄을 넘으면 줄 끝에 ▼ 를 더 넣어 쪽을 나눔(번역을 깎지 않음) — 쪽 마지막 줄은 ▼ 자리 1칸 비움
       ★이어 흘리기(2026-10-25 실기 «아기가»·«있으면» 한 낱말 줄): 원문 조각이 «꽉 찬 줄 자동 넘김»으로 끝나고 다음 조각이 들여쓰기(　)로
         이어지면(next_cont) 줄을 강제로 바꾸지 않음 — 원문 {n} 으로 끝나도(일본어 줄 길이에 맞춘 줄바꿈) ▼ 가 없으면 같음 → 다음 조각은 soft_in 으로 같은 줄에 띄어쓰기 하나 두고 이어 씀(들여쓰기 버림)."""
    bad = []
    s_it = items(src)
    lead_src = len(src) - len(src.lstrip(SPACE))
    hard = re.split(r'\{n\}', tr)
    if hard and hard[-1] == '': hard.pop()                          # 끝 {n} 은 원문 기준으로 다시 정함
    out = []; st = {'col': col0, 'quote': quote0, 'pl': pl0}

    def width():
        return W - 1 if st['pl'] >= PAGE else W

    def brk():
        if st['pl'] >= PAGE:
            out.append(('w',)); st['col'] += 1; st['pl'] = 0
        if not (st['col'] >= W and out and out[-1][0] != 'w'): out.append(('n',))
        st['col'] = 0; st['pl'] += 1

    def emit(ck):
        out.extend(ck); st['col'] += sum(cells(x) for x in ck)
        for x in ck:
            if x[0] == 'c' and x[1] in OPEN: st['quote'] += 1
            elif x[0] == 'c' and x[1] in CLOSE: st['quote'] = max(0, st['quote'] - 1)
            elif x[0] == 'w': st['pl'] = 0

    for hi, line in enumerate(hard):
        if hi: brk()
        it = items(line)
        lead = 0
        while lead < len(it) and it[lead] == ('c', SPACE): lead += 1
        body = it[lead:]
        ow = sum(cells(x) for x in s_it if x[0] != 'n')
        if hi == 0 and lead_src >= 2 and len(hard) == 1 and ow > W:   # 창 폭으로 설명 안 되는 원문(엔딩 크레디트 등) — 그대로, 원문 길이까지
            lim = max(ow, wsp)                                       # 같은 화면(사슬) 원문 가장 넓은 줄까지
            tw = sum(cells(x) for x in body); otw = ow - lead_src    # 가운데 맞춤 유지: 공백 수를 다시 셈
            it = [('c', SPACE)] * max(0, min(lead_src + (otw - tw) // 2, lim - tw)) + body
            w = sum(cells(x) for x in it)
            if w > lim: bad.append('특수 배치(엔딩 등 가운데 맞춤) 줄이 같은 화면 원문 가장 넓은 줄보다 김 %d>%d칸' % (w, lim))
            emit(it); continue
        ob = 0                                                      # 첫 조각이 「（ 처럼 겹 괄호로 열면 이어지는 줄은 그 수만큼(원문 «　　だな）」» 꼴)
        while hi == 0 and lead_src == 0 and ob < len(it) and it[ob][0] == 'c' and it[ob][1] in OPEN + '(': ob += 1
        ind = [('c', SPACE)] * max(1, min(lead_src or ob, 4))      # 들여쓰기: 원문 첫머리 공백 수(겹 괄호 2칸 등)
        if st['col'] == 0:
            if hi == 0 and lead_src >= 1: body = ind + body
            elif hi > 0 and (st['quote'] or lead): body = ind + body
        # 끊을 수 있는 덩어리: 공백에서(공백은 버림) · 부호 뒤
        chunks = []; cur = []
        for x in body:
            if x == ('c', SPACE) and cur and cur != [('c', SPACE)] * len(cur):
                chunks.append((cur, True)); cur = []; continue
            cur.append(x)
            if x[0] == 'c' and x[1] in PUNCT and x[1] not in '・':
                chunks.append((cur, False)); cur = []
        if cur: chunks.append((cur, False))
        merged = []
        for ck, sp in chunks:
            glue = all(x[0] in ('w', 'x') for x in ck) or (ck[0][0] == 'c' and ck[0][1] in PUNCT and ck[0][1] != '・')
            if merged and not merged[-1][1] and glue: merged[-1] = (merged[-1][0] + ck, sp)   # 닫는 괄호·부호·▼ 는 앞 낱말에 붙임
            else: merged.append((ck, sp))
        pend_space = bool(soft_in and hi == 0 and st['col'] > 0 and join_sp)   # 앞이 부호로 끝났거나 낱말 한가운데서 갈렸으면 붙여 이음
        for ck, sp in merged:
            w = sum(cells(x) for x in ck)
            if st['col'] > 0 and st['col'] + w + (1 if pend_space else 0) > width():
                brk()
                if st['quote'] or lead_src: emit(ind)
            elif pend_space and st['col'] > 0:
                emit([('c', SPACE)])
            if st['col'] + w > width():
                bad.append('낱말이 한 줄(%d칸)보다 김: %s' % (width(), unitems(ck)))
            emit(ck)
            pend_space = sp
    # 원문이 «꽉 찬 줄 + 다음 문장 «　▼»» 꼴이면(자동 줄바꿈 우연) 줄을 끝내지 않고 ▼ 를 이 줄 끝에 붙임
    explicit = bool(s_it and s_it[-1][0] == 'n')
    auto = not explicit and orig_ends_line(s_it, W, ocol0)
    waited = any(x[0] == 'w' for x in s_it[-2:]) or any(x[0] == 'w' for x in out[-1:])
    soft = (explicit or auto) and next_cont and not waited          # ▼ 없이 다음 조각이 들여쓰기로 이어지는 같은 말 — 한국어는 이어 흘림
    ends = (explicit and not soft) or (auto and not join_next and not soft)
    if ends and not (st['col'] >= W and (not out or out[-1][0] != 'w')):
        out.append(('n',)); st['col'] = 0; st['pl'] += 1
    return out, bad, st['pl'], soft


# ───────── 스크립트 순서(창·이어짐) ─────────
def script_places(d):
    """장면 블록의 참조를 스크립트 순서로 → [(사슬 번호, 블록, 위치, 창 폭, 참조 위치)] — 0x21 (얼굴 번호 | FFFFFFFF) 이 새 창"""
    blk = X.blocks(d); out = []; chain = 0
    for bi in sorted(blk):
        o, s = blk[bi]; b = d[o:o + s]
        ws = [struct.unpack_from('>I', b, k)[0] for k in range(0, s - 3, 4)]
        face = None; chain += 1
        for i, w in enumerate(ws):
            if w == 0x21 and i + 1 < len(ws) and (ws[i + 1] == 0xFFFFFFFF or ws[i + 1] < 0x100):
                face = ws[i + 1]; chain += 1
            if w >> 16 == 0x1000 | (bi - 2000):
                off = (w & 0xFFFF) * 4
                if off < 0x20 or off >= s or b[off] < 0x80 or not X.read_str(b, off): continue
                if bi < 2016 or face is None: W = None
                else: W = W_WIDE if face == 0xFFFFFFFF else W_FACE
                out.append((chain, bi, off, W, i * 4))
    return out


def sys_width(bi, src):
    if bi == 2015: return W_SYS
    if bi == 2014 and '{n}' in src: return W_SYS
    return None                                                     # 이름·메뉴: 원문 길이 경고만


# ───────── 입력 ─────────
def load_src():
    rows = collections.OrderedDict()
    for f in sorted(glob.glob(os.path.join(SRC, '번역할것_*.tsv'))):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln: c = ln.split('\t'); rows[c[0]] = c[1]
    locs = {}
    for ln in open(os.path.join(SRC, '_위치.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if ln:
            n, l = ln.split('\t'); locs[n] = [(int(a), int(b, 16)) for a, b in (x.split(':') for x in l.split())]
    return rows, locs


def load_tr(paths, src):
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, '*.tsv'))) if os.path.isdir(p) else [p]
    tr = {}; bad = []
    for f in files:
        lines = open(f, encoding='utf-8-sig').read().split('\n')
        head = lines[0].split('\t')
        if '번호' not in head or '번역' not in head: continue
        ino, isrc, itr = head.index('번호'), head.index('원문'), head.index('번역')
        for k, ln in enumerate(lines[1:], 2):
            if not ln.strip(): continue
            c = ln.split('\t')
            if len(c) <= itr or not c[itr]: continue
            n = c[ino].strip().zfill(5)
            where = '%s:%d' % (os.path.basename(f), k)
            if n not in src: bad.append((n, where, '번호가 번역할것에 없음')); continue
            if c[isrc] != src[n]: bad.append((n, where, '원문 칸이 번역할것과 다름(줄 어긋남?)')); continue
            if n in tr and tr[n][0] != c[itr]: bad.append((n, where, '같은 번호 번역이 둘 (%s)' % tr[n][1])); continue
            tr[n] = (c[itr], where)
    return tr, bad


JOSA = [('라는', '이라는'), ('라고', '이라고'), ('였던', '이었던'), ('였다', '이었다'), ('였', '이었'), ('라면', '이라면'), ('랑', '이랑'),
        ('는', '은'), ('가', '이'), ('를', '을'), ('와', '과'), ('로', '으로'), ('야', '아'), ('여', '이여'), ('라', '이라'), ('다', '이다')]


def has_batchim(w):
    c = w[-1]
    return '가' <= c <= '힣' and (ord(c) - 0xAC00) % 28 != 0


def replace_josa(t, a, b):
    """a → b 바꾸면서 바로 뒤 조사를 b 받침에 맞춤(전프로젝트 규칙: 용어 바꾸기는 뒤 조사까지)"""
    if has_batchim(a) == has_batchim(b): return t.replace(a, b)
    out = []; p = 0
    for m in re.finditer(re.escape(a), t):
        out.append(t[p:m.start()]); out.append(b); p = m.end()
        for x, y in JOSA:
            nb, wb = (x, y) if not has_batchim(a) else (y, x)       # a 받침 없음 → 있음: x→y
            if t.startswith(nb, p) and not (p + len(nb) < len(t) and '가' <= t[p + len(nb)] <= '힣' and nb in ('가', '다', '라', '야', '여') and False):
                out.append(wb); p += len(nb); break
    out.append(t[p:])
    return ''.join(out)


def apply_fixes(tr, src):
    """data/용어.tsv(원어 «*»=모든 줄 | 원문에 원어 있는 줄만: 틀린꼴→바른꼴) 다음 data/고침.tsv(번호→번역 통째)
       → 바꾼 번역, 막을 것(고침 뒤에도 틀린꼴 남음·고침 번호 없음), 바뀐 줄 수"""
    rules = []; fx = {}; bad = []
    p = os.path.join(ROOT, 'data', '용어.tsv')
    if os.path.exists(p):
        for ln in open(p, encoding='utf-8-sig').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 3 and c[1]: rules.append((c[0], c[1], c[2]))
    p = os.path.join(ROOT, 'data', '고침.tsv')
    if os.path.exists(p):
        for k, ln in enumerate(open(p, encoding='utf-8-sig').read().split('\n')[1:], 2):
            c = ln.split('\t')
            if len(c) >= 2 and c[0]:
                if c[0] not in src: bad.append((c[0], '고침.tsv:%d' % k, '번호가 번역할것에 없음')); continue
                fx[c[0]] = (c[1], '고침.tsv:%d' % k)
    out = {}; n = 0
    for no, (t, where) in tr.items():
        t2 = t
        for k, a, b in rules:
            if k == '*' or k in src[no]: t2 = replace_josa(t2, a, b)
        if no in fx: t2, where = fx[no]
        for k, a, b in rules:
            if (k == '*' or k in src[no]) and a in t2: bad.append((no, where, '용어 «%s» 남음(→%s)' % (a, b)))
        if t2 != t: n += 1
        out[no] = (t2, where)
    for no, v in fx.items():
        if no not in out: out[no] = v; n += 1
    return out, bad, n


def fake(src, k=1.0):
    """가짜 한글: 원문 글자 수 그대로(부호·토큰·괄호는 원문), 4글자마다 띄어쓰기"""
    out = {}
    for n, s in src.items():
        j = 0; cnt = 0.0; t = []
        for x in items(s):
            if x[0] == 'c' and re.match('[ぁ-んァ-ヶ一-龥々〆ー]', x[1]):
                for _ in range(int(cnt + k) - int(cnt)):
                    t.append(' ' if j % 5 == 4 else '가나다라마바사'[j % 7]); j += 1
                cnt += k
            else: t.append(unitems([x]))
        out[n] = (''.join(t), 'fake')
    return out


# ───────── 본체 ─────────
GLUE = set()                                                        # data/붙여잇기.tsv — 낱말 한가운데서 갈린 조각(않{n}으니까), tools/join_check.py 가 만듦
if os.path.exists(os.path.join(ROOT, 'data', '붙여잇기.tsv')):
    GLUE = {tuple(l.split('\t')[:2]) for l in open(os.path.join(ROOT, 'data', '붙여잇기.tsv'), encoding='utf-8-sig').read().split('\n')[1:] if l.strip()}
JOINS = []                                                          # 이어 흘린 자리(앞 번호, 뒤 번호, 앞 번역, 뒤 번역, 위치) — work/tr/joins.tsv


def main(argv):
    banner()
    src, locs = load_src()
    fk = [a for a in argv if a.startswith('--fake')]
    if fk: tr, bad_in = fake(src, float(fk[0].split('=')[1]) if '=' in fk[0] else 1.0), []
    else:
        paths = [a for a in argv if not a.startswith('--')] or [TRDIR]
        tr, bad_in = load_tr(paths, src)
        tr, bad_fx, nfix = apply_fixes(tr, src); bad_in += bad_fx
        print('용어 바꿈·고침 %d줄 (data/용어.tsv · data/고침.tsv)' % nfix)
    probs = [(n, w, m) for n, w, m in bad_in]; warns = []
    clean = {}
    for n, (t, where) in tr.items():
        t2, bad, wn = check(src[n], t)
        probs += [(n, where, m) for m in bad]; warns += [(n, where, m) for m in wn]
        if not bad: clean[n] = t2
    # 위치 → 번호
    at = {}
    for n, ls in locs.items():
        for l in ls: at[l] = n
    d = open(os.path.join(ROOT, 'work', 'disc', 'GUN.AD2'), 'rb').read()
    final = {}                                                      # (블록, 위치) → 최종 문자열
    # 장면: 사슬마다 창 흉내 — 같은 문장을 다른 곳(창·앞 문장)에서 부르면 참조별 사본(ref)
    places = script_places(d); BLK = X.blocks(d)
    by_chain = collections.OrderedDict()
    for ch, bi, off, W, rp in places: by_chain.setdefault(ch, []).append((bi, off, W, rp))
    lists = {}; ref_var = {}                                       # (블록, 위치) → 항목[] / (블록, 참조 위치) → 항목[]
    for ch, pl in by_chain.items():
        cu_o = cu_k = None; prev = None; kmax = (0, None, 0, 0); omax = 0; last_soft = False
        nest = 0; last_n = None                                     # 원문 괄호 깊이(「『（) — 겹 괄호 안 이어지는 줄은 들여쓰기 2칸
        wsp = 0                                                     # 이 사슬 원문 가장 넓은 줄(가운데 맞춤 화면 폭 기준)
        for bi, off, W, rp in pl:
            if W is None: continue
            o_, z_ = BLK[bi]; r_ = X.read_str(d[o_:o_ + z_], off)
            if r_: wsp = max([wsp] + [len(TOK.sub('', x)) for x in r_[0].split('{n}')])
        for k_, (bi, off, W, rp) in enumerate(pl):
            n = at.get((bi, off))
            if W is None: continue
            if n is None:                                           # 번역할것에 없는 문장(«　{w}{n}» 같은 토큰뿐) — 원문 그대로 흉내
                o, sz = BLK[bi]
                s = X.read_str(d[o:o + sz], off)[0]
            else: s = src[n]
            s_it = items(s)
            if cu_o is None: cu_o, cu_k = Cursor(W), Cursor(W)
            if cu_k.col == 0 and cu_k.lines > PAGE and prev is not None and prev[-1] == ('n',) and (len(prev) < 2 or prev[-2] != ('w',)):
                prev.insert(len(prev) - 1, ('w',))                  # 앞 문장 끝에 ▼ — 이 문장부터 새 쪽
                cu_k.maxpage = max(cu_k.maxpage, cu_k.lines - 1); cu_k.lines = 1
            if n in clean:
                nx = pl[k_ + 1] if k_ + 1 < len(pl) else None
                nxs = X.read_str(d[BLK[nx[0]][0]:BLK[nx[0]][0] + BLK[nx[0]][1]], nx[1])[0] if nx else ''
                tok_only = bool(nxs) and TOK.sub('', nxs).strip(SPACE) == '' and '{w}' in nxs
                for c in TOK.sub('', s):
                    if c in '「『（': nest += 1
                    elif c in '」』）': nest = max(0, nest - 1)
                L = len(nxs) - len(nxs.lstrip(SPACE))
                next_cont = bool(nxs) and 1 <= L <= max(1, nest) and not tok_only
                join_sp = True
                if last_soft:
                    pt = re.sub(r'(\{[^{}]*\})+$', '', clean[last_n]).rstrip(SPACE)
                    join_sp = not (pt[-1:] in PUNCT or (last_n, n) in GLUE)
                it, bad, _, soft = layout(clean[n], s, W, cu_k.col if cu_k.col < W else 0, cu_k.quote,
                                    cu_o.col if cu_o.col < W else 0, cu_k.lines + (cu_k.col >= W), tok_only, wsp,
                                    soft_in=last_soft, next_cont=next_cont, join_sp=join_sp)
                if last_soft: JOINS.append((last_n, n, clean[last_n], clean[n], '%d:%X' % (bi, off)))
                last_soft = soft; last_n = n
                probs += [(n, tr[n][1], m + ' @%d:%X' % (bi, off)) for m in bad]
                if (bi, off) not in lists: lists[(bi, off)] = it; prev = it
                elif lists[(bi, off)] == it: prev = lists[(bi, off)]
                else: ref_var[(bi, rp)] = it; prev = it
            else:
                it = s_it; prev = None; last_soft = False
                for c in TOK.sub('', s):
                    if c in '「『（': nest += 1
                    elif c in '」』）': nest = max(0, nest - 1)
            cu_o.feed(s_it); cu_k.feed(it)
            pk = max(cu_k.maxpage, cu_k.lines - (cu_k.col == 0))      # {n} 뒤 빈 줄은 아직 안 씀
            if pk > kmax[0]: kmax = (pk, n, bi, off)
            omax = max(omax, cu_o.maxpage, cu_o.lines - (cu_o.col == 0))
        if cu_k and kmax[0] > PAGE and kmax[0] > omax and kmax[1] in clean:   # 사슬(창 하나) 안 가장 긴 쪽이 4줄 넘고 원문보다 김
            n, bi, off = kmax[1:]
            probs.append((n, tr[n][1], '한 쪽 %d줄(원문 가장 긴 쪽 %d줄, 창 %d줄) @%d:%X' % (kmax[0], omax, PAGE, bi, off)))
    for k, it in lists.items(): final[k] = unitems(it)
    final_ref = {k: unitems(it) for k, it in ref_var.items()}
    # 그 밖(시스템·오프닝·사슬 밖)
    for (bi, off), n in at.items():
        if (bi, off) in final or n not in clean: continue
        s = src[n]; W = sys_width(bi, s)
        if W is None:
            if len(TOK.sub('', clean[n])) > len(TOK.sub('', s)):
                warns.append((n, tr[n][1], '이름·메뉴가 원문보다 김 %d>%d칸 — 실기 확인' % (len(TOK.sub('', clean[n])), len(TOK.sub('', s)))))
            final[(bi, off)] = clean[n]; continue
        it, bad, _, _ = layout(clean[n], s, W, 0, 0)
        probs += [(n, tr[n][1], m + ' @%d:%X' % (bi, off)) for m in bad]
        final[(bi, off)] = unitems(it)
    # 보고
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'joins.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('앞\t뒤\t앞 번역\t뒤 번역\t위치\n')
        for j in JOINS: w.write('\t'.join(j) + '\n')
    rep = os.path.join(OUT, 'report.tsv')
    with open(rep, 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('구분\t번호\t위치\t내용\t원문\t번역\n')
        for kind, lst in (('막음', probs), ('경고', warns)):
            for n, where, m in lst:
                w.write('%s\t%s\t%s\t%s\t%s\t%s\n' % (kind, n, where, m, src.get(n, ''), tr.get(n, ('',))[0]))
    hang = sorted({c for v in clean.values() for c in v if '가' <= c <= '힣'})
    print('번역 %d/%d줄 · 통과 %d · 막음 %d건 · 경고 %d건 · 한글 %d자(칸 %d) · 위치 %d곳'
          % (len(tr), len(src), len(clean), len(probs), len(warns), len(hang), 32 * 94 - 94, len(final)))
    for n, where, m in probs[:30]: print('  ✗ %s %s %s' % (n, where, m))
    if len(probs) > 30: print('  … 나머지는', rep)
    if probs:
        print('❌ 막힌 줄이 있어 places.tsv 를 쓰지 않음 →', rep); return False
    with open(os.path.join(OUT, 'places.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('블록\t위치\t참조\t번호\t최종\n')                  # 참조 «*» = 그 문장을 부르는 모든 참조, 16진 = 그 참조만(사본)
        for (bi, off), s in sorted(final.items()):
            w.write('%d\t%X\t*\t%s\t%s\n' % (bi, off, at[(bi, off)], s))
        for (bi, rp), s in sorted(final_ref.items()):
            w.write('%d\t\t%X\t\t%s\n' % (bi, rp, s))
    print('✅ →', os.path.join(OUT, 'places.tsv'), '/ 보고', rep); return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(sys.argv[1:]) else 1)
