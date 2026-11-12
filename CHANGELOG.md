# Changelog

## 1.0.4

- New: **picture guide for manual port forwarding**. Twelve drawn steps, each filled in with your own router
  address, this PC's IP and the ports, with a pointer showing where to click: how it works, the router's port
  forwarding rule and DHCP reservation, then a **Windows Defender Firewall inbound rule made by hand**
  (Control Panel → Advanced settings → Inbound Rules → New Rule → Port → TCP 25565 → Allow → name → Finish),
  and the test from outside. The text version is still one click away.
- Automatic port forwarding now works the way established programs do it (miniupnpc, libtorrent,
  Syncthing, Windows' own NAT API):
  - the UPnP search goes out of every network adapter (VPN / Hyper-V / VirtualBox adapters no longer hide the
    router) and straight to the default gateway;
  - the right router is picked like miniupnpc's "valid IGD": connected, with a routable external IP,
    preferring the default gateway;
  - more lease fallbacks, and our own stale mapping (this PC got a new IP) is replaced instead of failing
    with error 718; someone else's mapping is never touched;
  - **PCP / NAT-PMP** fallback (UDP 5351) for routers with UPnP off;
  - on Windows, a last try through the system's UPnP service (HNetCfg.NATUPnP).
  - a PC that has a public IP itself (no router, straight on the ISP line) is recognised: nothing to
    forward, only the firewall matters.
- Fixed: ports below 1024 were accepted. Server, RCON and query ports now must be 1024–65535 (lower ports
  belong to system services); RCON can't share the game port; a port already in use on this PC is pointed
  out on the Location step and in the review. Old saved values are clamped.
- Downloads behave like a download manager: if the server stops sending for 20 s or drops the connection,
  the installer reconnects and continues where it stopped (up to 5 times), and the log shows size, speed and time left.
- Fixed: reading the output of netsh / PowerShell on Korean (cp949) and other non-UTF-8 Windows crashed a
  background thread and lost the result (gateway address, firewall check, Windows UPnP).
- New: **Windows Firewall rules are added during install** (one administrator prompt, skipped when the rules
  already exist; checked with Get-NetFirewallRule). The done page warns when they could not be added. Can be turned off under Manage & launch; open_firewall.bat is still written.

## 1.0.3

- New: **update notice**. At startup the installer checks GitHub and offers the new version
  (Download / Later / Skip this version). Can be turned off in ⚙ Settings.
- New: **limited-time event loaders**. Joke server types that appear only around their event:
  Pumpkin Loader (Halloween), Jingle Loader (Christmas), Firework Loader (New Year),
  Cocoa Loader (Valentine's Day), Prank Loader (April Fools' Day) and UFO Loader (World UFO Day).
  Each has its own 3D animation (UFO Loader has the UFO borrow the menu for a moment). Pick one and press
  Next: only the folder, review, install and done steps remain, and the folder opens when it is done.
  Its `start.bat`/`start.sh` opens a window with a short 3D animation (drawn in plain Java) and exits;
  without a screen it plays a console animation instead. Every loader has its own
  GitHub release (`event-halloween`, ...). A notice announces a new event loader once. New events can be added later without
  an app update. *⚙ Settings → Show event loaders all year* shows them any time.
- README: step-by-step help for the "Windows protected your PC" warning.
- CI: GitHub Actions updated to the Node.js 24 versions.

## 1.0.2

- Fixed: the 3D (OpenGL) background did not start in the 1.0.1 `.exe` ("3D effects: not supported").
  The bundled PyOpenGL 3.1.10 returns uniform names as a byte array on Windows, which the code did not expect.
- Fixed: the 3D background failed (`NullFunctionError`) when Qt renders with a different OpenGL DLL than
  the system one, e.g. its software fallback on virtual machines, remote desktop or weak drivers.
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
