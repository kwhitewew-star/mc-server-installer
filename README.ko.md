# MC Server Installer

[English](README.md) · **한국어**

마인크래프트 자바 에디션 서버를 단계별로 설치하는 데스크톱 프로그램입니다. 서버 종류와 버전을 고르고
원하는 만큼 설정을 바꾸면, 파일 다운로드와 설정 파일 작성, 공유기 포트 열기, 첫 실행 확인까지 알아서 합니다.

![MC Server Installer](docs/screenshots/hero.jpg)

## 기능

- **서버 16종**: Vanilla, Paper, Purpur, Folia, Spigot, Bukkit · Fabric, Quilt, Legacy Fabric, Babric,
  Forge, NeoForge · 하이브리드 Mohist, Youer, Arclight, Banner.
  버전과 빌드 목록은 각 프로젝트의 공식 API에서 실시간으로 받아옵니다.
- **설정 모드 3가지**: 빠른(종류·버전·폴더만), 중간(자주 쓰는 43개), 상세(`server.properties` 전체,
  게임 규칙, 실행 옵션까지 144개). 검색과 분류를 지원합니다.
- **버전별 처리**: 26.x 연도 방식 버전, 버전별 필요한 Java, 1.21.9에서 게임 규칙으로 옮겨진 항목,
  1.21.11부터의 snake_case 게임 규칙 이름을 자동으로 맞춥니다.
- **모드·플러그인**: Modrinth에서 내 로더와 버전에 맞는 것만 검색하고 필수 의존성을 자동으로 추가합니다.
  내 `.jar`/`.zip` 파일도 넣을 수 있습니다.
- **Java**: 설치된 Java(마인크래프트 런처 포함)를 찾고, 없으면 Temurin JDK를 받아 줍니다.
- **포트포워딩**: UPnP로 필요한 포트를 자동으로 엽니다. 공유기가 막혀 있으면 내 네트워크 값
  (공유기 주소, 이 PC의 IP, 포트와 프로토콜)을 채운 수동 설정 방법, 주요 공유기별 메뉴 위치,
  이중 공유기·CGNAT 확인 방법을 안내합니다.
- **편의 기능**: 자동 재시작 옵션이 있는 `start.bat`/`start.sh`, Aikar 플래그, 백업 스크립트,
  방화벽 스크립트, 바탕화면 바로가기, 서버 아이콘, OP·화이트리스트.
- **첫 실행 확인**: 서버를 한 번 켜서 콘솔로 게임 규칙·OP·화이트리스트를 적용한 뒤 정상 종료합니다.
- **언어**: English, 한국어, 日本語, 简体中文, Español.
- OpenGL 실시간 유리 배경(굴절, 입자, 서버 종류별 애니메이션). OpenGL을 쓸 수 없으면 2D 배경으로 바뀝니다.

| 포트포워딩 안내 |
| --- |
| ![포트포워딩](docs/screenshots/ko_port_guide.png) |

## 실행

**Python 3.10 이상**이 필요합니다. Java는 미리 없어도 됩니다.

**Windows**: `run.bat`을 더블클릭하세요. 처음 실행할 때 필요한 패키지를 설치합니다.

**Linux / macOS**: `./run.sh`

**직접 실행**:

```bash
python -m pip install -r requirements.txt
python run.py            # 또는: python -m mcsi
```

기본 언어는 영어입니다. **⚙ 설정 → Language**에서 한국어로 바꿀 수 있습니다.
설정은 `~/.mc_server_installer/config.json`에 저장됩니다.

서버를 설치하면 [마인크래프트 EULA](https://aka.ms/MinecraftEULA)에 동의하는 것이며, 설치 전에 확인을 받습니다.

## 연결 테스트

버전 목록이 안 뜨면 `selftest.bat`(또는 `python scripts/selftest.py`)을 실행하세요. 모든 서버 종류의 API를
확인하고 결과를 `selftest_result.txt`에 저장합니다. 버그를 알릴 때 첨부하면 좋습니다.

## 개발

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python scripts/screenshots.py ko      # 모든 화면을 오프스크린으로 돌며 잘림 확인
python scripts/i18n_sync.py           # 언어별 빠진 번역 확인
```

번역은 `mcsi/i18n/<언어>.json`에 있으며, 영어 원문을 키로 씁니다. 자세한 내용은 [README.md](README.md#translations)를 보세요.

## 라이선스

[MIT](LICENSE). 마인크래프트 공식 제품이 아니며 Mojang·Microsoft와 관계가 없습니다.
서버 소프트웨어는 각 프로젝트의 서버에서 내려받으며 각자의 라이선스를 따릅니다.
