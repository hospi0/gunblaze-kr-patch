# 건블레이즈 S (GunBlaze-S, 세가 새턴 일본판) 한글 패치

배포: [Releases](../../releases) 의 `GunBlazeS_KR_v0.9.zip` — 트랙 1 xdelta + 적용 bat + readme.

- 원본 트랙 1 md5 `4546FF5145F6699E5959EFFB993821AB` → 패치 후 `97DD5A73B08A821B00A42DF5A1EFCD8F`
- 대사 전체·메뉴·아이템·전투·장소·저장 문구 한글화, 문장부호 한글식, HUD 탄약 글자.

## 빌드

1. `python tools/extract.py` — 원본 트랙 1 에서 파일 추출(work/disc)
2. `python tools/load_tr.py` — 번역(data/번역) 검사·조판 → work/tr/places.tsv
3. `python tools/build.py` — GUN.AD2 재구성(글꼴·문장·참조) → work/build/kr
4. `python tools/make_dist.py` — 배포 묶음

자세한 구조·이력은 `docs/00_초기조사.md`, `docs/00_이어하기.md`.
