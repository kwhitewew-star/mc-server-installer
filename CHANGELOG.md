# Changelog

## 1.0.2

- A failed 3D start is no longer saved as "Off": the installer tries again on the next launch, and
  clicking "3D effects" retries right away.
- The "3D effects: not supported" button now shows the reason; details are written to
  `~/.mc_server_installer/gl_error.log`.
- Release builds are now tested with a real (software) OpenGL renderer before they are published.

## 1.0.1

- Windows release builds: a single-file `.exe`, a portable zip and a source zip are attached to each
  GitHub release automatically.
- App icon, and the installer now shows its own icon in the taskbar.
- Switching the language restarts correctly from the packaged `.exe`.

## 1.0.0

First public release.

- 16 server types: Vanilla, Paper, Purpur, Folia, Spigot, Bukkit, Fabric, Quilt, Legacy Fabric, Babric,
  Forge, NeoForge, Mohist, Youer, Arclight, Banner.
- Quick / Standard / Detailed setup modes covering 144 settings.
- Modrinth search with automatic dependency resolution, plus local files.
- Automatic Java detection and Temurin JDK download.
- Automatic UPnP port forwarding with a manual guide filled in for your network.
- Verified first run that applies game rules, ops and whitelist.
- English (default), Korean, Japanese, Simplified Chinese and Spanish.
- OpenGL glass background with per-server-type animations, with a 2D fallback.
