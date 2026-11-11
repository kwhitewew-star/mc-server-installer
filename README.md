# MC Server Installer

**English** · [한국어](README.ko.md)

A step-by-step desktop installer for Minecraft Java Edition servers. You pick a server type and a version,
adjust as many or as few settings as you like, and it downloads everything, writes the config, opens your
router's port and starts the server once to check that it works.

![MC Server Installer](docs/screenshots/hero.jpg)

## Features

- **16 server types**: Vanilla, Paper, Purpur, Folia, Spigot, Bukkit · Fabric, Quilt, Legacy Fabric, Babric,
  Forge, NeoForge · hybrids Mohist, Youer, Arclight, Banner.
  Version and build lists come live from each project's official API (Mojang, PaperMC Fill v3, Purpur,
  Fabric/Quilt meta, Forge/NeoForge Maven, MohistMC, GitHub releases).
- **Three setup modes**: Quick (type, version, folder), Standard (43 common settings) and Detailed
  (all 144 options: the full `server.properties`, game rules and launch options), with search and grouping.
- **Version-aware**: knows the year-based 26.x versions, the Java each version needs, properties that moved
  to game rules in 1.21.9 and the snake_case game rule names of 1.21.11+.
- **Mods & plugins** from Modrinth, filtered to your loader and version, with required dependencies added
  automatically. Local `.jar`/`.zip` files work too.
- **Java**: finds installed Java (including the Minecraft Launcher's) and can download Temurin JDK for you.
- **Port forwarding**: opens the needed ports automatically over UPnP. If the router doesn't allow it,
  a guide shows the exact values for your network (router address, this PC's IP, every port and protocol),
  where the menu is on common routers, and how to recognize double NAT / CGNAT.
- **Extras**: `start.bat`/`start.sh` with optional auto-restart, Aikar's flags, backup scripts,
  a firewall script, desktop shortcut, server icon, ops and whitelist.
- **Verified first run**: starts the server once, applies game rules / ops / whitelist through the console,
  then stops it cleanly.
- **Languages**: English, 한국어, 日本語, 简体中文, Español.
- Glass UI with a real-time OpenGL background (refraction, particles, a short animation for each server
  type). It falls back to a plain 2D background when OpenGL isn't available.

| Mods & plugins | Port forwarding guide |
| --- | --- |
| ![Mods and plugins](docs/screenshots/addons.png) | ![Port forwarding](docs/screenshots/port_guide.png) |

## Getting started

You need **Python 3.10 or newer**. Java is not required in advance: the installer can download it.

**Windows**: double-click `run.bat`. It installs the Python packages on first launch.

**Linux / macOS**:

```bash
./run.sh
```

**Manually**:

```bash
python -m pip install -r requirements.txt
python run.py            # or: python -m mcsi
```

The language can be changed in **⚙ Settings → Language**. Settings are stored in
`~/.mc_server_installer/config.json`.

By installing a server you accept the [Minecraft EULA](https://aka.ms/MinecraftEULA); the installer asks
for this before it starts.

## Connection test

If version lists don't load, run `selftest.bat` (or `python scripts/selftest.py`). It checks every
provider's API and writes `selftest_result.txt`, which is handy to attach to a bug report.

## Project layout

```
mcsi/
  core/        installer engine, no GUI code
    providers.py   version lists and install logic for every server type
    installer.py   the install pipeline (download → config → extras → first run → UPnP)
    schema.py      every setting: server.properties, game rules, launch and extras
    modrinth.py    Modrinth search and dependency resolution
    upnp.py        UPnP IGD port forwarding (standard library only)
    java.py        Java detection and Temurin download
    net.py, versions.py
  ui/          PyQt6 windows, pages and widgets
  gfx/         OpenGL background, GLSL shaders and server animations
  i18n/        translation catalogs (<code>.json)
scripts/       selftest.py, screenshots.py, i18n_sync.py
tests/         offline tests with fake APIs and a fake Java
```

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest              # offline: fake APIs, fake Java, fake UPnP router
python -m pyflakes mcsi scripts tests
python scripts/screenshots.py ko      # walk through every page offscreen, check for clipped layouts
```

### Translations

All UI text is written in English and wrapped in `_("...")`. Each language is a JSON file in `mcsi/i18n/`
that maps the English text to the translation; missing entries fall back to English.

```bash
python scripts/i18n_sync.py           # what's missing in each language
python scripts/i18n_sync.py --new de  # start a new language
```

Then add the code to `LANGUAGES` in `mcsi/i18n/__init__.py`. Keep placeholders such as `{0}` and
`{1:,}` and any HTML tags exactly as they are; `tests/test_i18n.py` checks this.

## License

[MIT](LICENSE). Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
Server software is downloaded from each project's own servers and remains under its own license.
