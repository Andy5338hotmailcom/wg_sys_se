@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ================================================
echo   大雁系统 - wg_connect 生成 pycache
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 找不到 python，请先安装 Python 并把它加入 PATH。
    echo.
    goto :end
)

rem 关键两步：清掉这两个变量，pyc 才会落在本目录的 __pycache__ 里。
rem PYTHONPYCACHEPREFIX 一旦存在，所有 pyc 会被统一挪到那个缓存根下，本目录就永远是空的。
set "PYTHONPYCACHEPREFIX="
set "PYTHONDONTWRITEBYTECODE="

if exist "__pycache__" (
    echo 清理旧的 __pycache__ ...
    rmdir /s /q "__pycache__"
)

echo 正在编译 .py 为 __pycache__ ...
python -m compileall -q -f .
if errorlevel 1 (
    echo.
    echo [失败] 编译出错了，请检查上面的输出。
    goto :end
)

echo.
echo 生成结果：
if exist "__pycache__" (
    for %%f in ("__pycache__\*.pyc") do echo   %%~nxf
) else (
    echo   [空] 一个 pyc 都没生成
)

echo.
echo 说明：只有被 import 的模块才会产出 pyc，直接 python server.py 跑时它自己是 __main__，不会生成。
echo 所以这里用 compileall 主动把 server.py 和 test_server.py 都编一遍。
echo.

:end
if /i not "%~1"=="/q" pause
