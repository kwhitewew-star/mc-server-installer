"""Build the Windows release files with PyInstaller.

    python -m pip install -r requirements.txt pyinstaller
    python scripts/build_exe.py

Output in dist/:
    MC-Server-Installer-<version>.exe              single file, just double-click
    MC-Server-Installer-<version>-portable.zip     folder version (starts faster, fewer antivirus false alarms)
    mc-server-installer-<version>-source.zip       source code (only when run inside a git checkout)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcsi import __version__  # noqa: E402

NAME = "MC-Server-Installer"
DIST = ROOT / "dist"
SEP = os.pathsep        # PyInstaller --add-data uses ';' on Windows and ':' elsewhere


def version_file() -> Path:
    nums = (__version__.split(".") + ["0", "0", "0"])[:3]
    v = ", ".join(nums + ["0"])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v})),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'kwhitewew-star'),
    StringStruct('FileDescription', 'MC Server Installer'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', '{NAME}'),
    StringStruct('LegalCopyright', 'MIT License'),
    StringStruct('OriginalFilename', '{NAME}.exe'),
    StringStruct('ProductName', 'MC Server Installer'),
    StringStruct('ProductVersion', '{__version__}')])]),
  VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""
    path = ROOT / "build" / "version_info.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def pyinstaller(onefile: bool) -> None:
    args = [
        str(ROOT / "run.py"),
        "--name", NAME,
        "--noconfirm", "--clean", "--windowed",
        "--onefile" if onefile else "--onedir",
        "--distpath", str(DIST / ("onefile" if onefile else "onedir")),
        "--workpath", str(ROOT / "build" / ("onefile" if onefile else "onedir")),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{ROOT / 'mcsi' / 'i18n'}{SEP}mcsi/i18n",
        "--add-data", f"{ROOT / 'mcsi' / 'assets'}{SEP}mcsi/assets",
        "--collect-submodules", "OpenGL",       # PyOpenGL picks its platform module at runtime
        "--collect-data", "certifi",
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
    ]
    if sys.platform == "win32":
        args += ["--icon", str(ROOT / "mcsi" / "assets" / "icon.ico"), "--version-file", str(version_file())]
    PyInstaller.__main__.run(args)


def zip_dir(src: Path, dest: Path, prefix: str) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                z.write(f, f"{prefix}/{f.relative_to(src).as_posix()}")


def main() -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    exe = ".exe" if sys.platform == "win32" else ""

    pyinstaller(onefile=True)
    one = DIST / f"{NAME}-{__version__}{exe}"
    shutil.move(str(DIST / "onefile" / f"{NAME}{exe}"), one)

    pyinstaller(onefile=False)
    portable = DIST / f"{NAME}-{__version__}-portable.zip"
    zip_dir(DIST / "onedir" / NAME, portable, NAME)

    if (ROOT / ".git").exists():
        src = DIST / f"mc-server-installer-{__version__}-source.zip"
        subprocess.run(["git", "archive", "--format", "zip", "--prefix", f"mc-server-installer-{__version__}/",
                        "-o", str(src), "HEAD"], cwd=ROOT, check=True)

    shutil.rmtree(DIST / "onefile", ignore_errors=True)
    shutil.rmtree(DIST / "onedir", ignore_errors=True)
    for f in sorted(DIST.iterdir()):
        print(f"{f.name:52s} {f.stat().st_size / 1e6:7.1f} MB")


if __name__ == "__main__":
    main()
