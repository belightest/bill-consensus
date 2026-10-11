"""PyInstaller 打包入口。

为什么需要这个文件:
  直接用 bill_consensus/main.py 打包时,包内相对导入的静态分析不够可靠。
  用一个顶层启动器 + 绝对导入,PyInstaller 能 100% 追踪所有模块依赖。

用法:
  python launcher.py [参数...]          # 和 python -m bill_consensus.main 等价
  pyinstaller launcher.spec             # 打包成 exe(见 build_exe.bat)
"""
from bill_consensus.main import main

if __name__ == "__main__":
    main()
