# Windows 部署自动化脚本

Write-Host "--- 开始部署 PictureWeb 系统 ---" -ForegroundColor Cyan

# 1. 检查环境
Write-Host "1. 检查基础环境..." -ForegroundColor Yellow
if (!(Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 Node.js，请先安装。"
    exit 1
}
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 Python，请先安装。"
    exit 1
}

# 2. 前端构建
Write-Host "2. 构建前端应用..." -ForegroundColor Yellow
Push-Location web
npm config set registry https://registry.npmmirror.com
npm install
npm run build
Pop-Location

# 3. 后端环境准备
Write-Host "3. 准备后端环境..." -ForegroundColor Yellow
if (!(Test-Path venv)) {
    python -m venv venv
}
.\venv\Scripts\Activate.ps1
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com
pip install -r server/requirements.txt
pip install waitress

# 4. 数据目录初始化
Write-Host "4. 初始化数据目录..." -ForegroundColor Yellow
if (!(Test-Path data)) {
    New-Item -ItemType Directory -Path data
}
if (!(Test-Path data/cache)) {
    New-Item -ItemType Directory -Path data/cache
}

# 5. 检查配置文件
if (!(Test-Path config.yaml)) {
    Write-Host "创建默认配置文件 config.yaml..." -ForegroundColor Gray
    Copy-Item server/config.example.yaml config.yaml -ErrorAction SilentlyContinue
}

Write-Host "--- 部署完成！ ---" -ForegroundColor Green
Write-Host "您可以运行 'python prod_run.py' 启动生产环境。" -ForegroundColor White
