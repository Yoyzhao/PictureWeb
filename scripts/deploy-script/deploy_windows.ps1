# Windows 部署自动化脚本

Write-Host "--- 开始部署 PicGallery ---" -ForegroundColor Cyan

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

# 1. 检查环境
Write-Host "1. 检查基础环境..." -ForegroundColor Yellow
if (!(Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 Node.js，请先安装。"
    exit 1
}
$python = "py -3.12"
try { Invoke-Expression "$python --version" | Out-Null } catch {
    Write-Error "未找到 Python 3.12（py -3.12），请先安装。"
    exit 1
}

# 2. 本地配置
Write-Host "2. 检查本地配置..." -ForegroundColor Yellow
if (!(Test-Path config.yaml)) {
    Write-Host "创建默认开发配置 config.yaml..." -ForegroundColor Gray
    Copy-Item config.example.yaml config.yaml
}
if (!(Test-Path .env)) {
    Write-Host "未找到 .env，请从 .env.example 复制并填写 SECRET_KEY、DEFAULT_ADMIN_USERNAME、DEFAULT_ADMIN_PASSWORD。" -ForegroundColor Red
    exit 1
}

# 3. 前端构建
Write-Host "3. 构建前端应用..." -ForegroundColor Yellow
Push-Location web
npm config set registry https://registry.npmmirror.com
npm install
npm run build
Pop-Location

# 4. 后端环境准备（虚拟环境固定在 server/venv）
Write-Host "4. 准备后端环境..." -ForegroundColor Yellow
if (!(Test-Path server\venv)) {
    py -3.12 -m venv server\venv
}
& .\server\venv\Scripts\python.exe -m pip install --upgrade pip
& .\server\venv\Scripts\python.exe -m pip install -r server\requirements.txt

# 5. 数据目录初始化
Write-Host "5. 初始化数据目录..." -ForegroundColor Yellow
foreach ($dir in @("data/db", "data/cache", "data/trash", "data/app_logs")) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

# 6. 初始化数据库（已有库不会覆盖管理员密码）
Write-Host "6. 初始化数据库..." -ForegroundColor Yellow
& .\server\venv\Scripts\python.exe scripts\sql-script\init_db.py

Write-Host "--- 部署完成！ ---" -ForegroundColor Green
Write-Host "开发环境可运行 'python server/run.py'；生产环境请在部署副本中运行 'python prod_run.py'。" -ForegroundColor White
