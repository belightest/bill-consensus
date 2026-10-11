# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 —— 生成单文件 exe「账单合并工具.exe」

用法:
    python -m PyInstaller bill_consensus_exe.spec --noconfirm --clean
或直接双击 build_exe.bat

产物:
    dist/账单合并工具.exe   (单文件,无需安装 Python 即可运行)

说明:
    - launcher.py 是打包专用入口(绝对导入,便于 PyInstaller 追踪依赖)
    - templates/ 仪表盘模板作为数据文件打进 exe
    - 用户数据(bills/、output/)运行时生成在 exe 同级目录,不打进包
"""
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # 仪表盘模板(Jinja2 运行时读取)
        ('bill_consensus/templates', 'bill_consensus/templates'),
    ],
    hiddenimports=[
        'bill_consensus',
        'bill_consensus.main',
        'bill_consensus.parsers',
        'bill_consensus.parsers.base',
        'bill_consensus.parsers.smart_csv',
        'bill_consensus.parsers.wechat',
        'bill_consensus.parsers.alipay',
        'bill_consensus.parsers.bank',
        'bill_consensus.parsers.image_ocr',
        'bill_consensus.parsers.factory',
        'bill_consensus.analyzer',
        'bill_consensus.analyzer.classifier',
        'bill_consensus.analyzer.statistics',
    ] + collect_submodules('openpyxl'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除与本项目无关的重型库,显著减小体积
    excludes=[
        'tkinter', 'matplotlib', 'pytest', 'IPython', 'notebook',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'sqlalchemy', 'numba', 'scipy',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='账单合并工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # UPX 压缩容易触发杀软误报,默认关闭
    upx_exclude=[],
    runtime_tmpdir=None,      # 单文件模式:运行时解压到临时目录
    console=True,             # 保留控制台,能看到解析进度
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                # 如需自定义图标: icon='icon.ico'
)
