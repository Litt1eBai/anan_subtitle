from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path(SPECPATH).resolve()
entry_script = project_root / "src" / "main.py"

hiddenimports = sorted(
    set(
        collect_submodules("funasr")
        + collect_submodules("modelscope")
    )
)

datas = [
    (str(project_root / "config" / "default.yaml"), "config"),
    (str(project_root / "config" / "base.png"), "config"),
]
datas += collect_data_files("funasr", includes=["**/*.yaml", "**/*.yml", "**/*.json", "**/*.txt"])
datas += collect_data_files("modelscope", includes=["**/*.yaml", "**/*.yml", "**/*.json", "**/*.txt"])

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="anan_subtitle",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="anan_subtitle",
)
