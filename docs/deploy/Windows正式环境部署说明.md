# Windows 正式环境部署说明

本文档详细说明了 PictureWeb 系统在 Windows 环境下的生产部署流程。

## 1. 环境准备

在开始部署之前，请确保系统中已安装以下软件：

- **Python 3.10+**: [下载地址](https://www.python.org/downloads/windows/)
- **Node.js v18+ & npm**: [下载地址](https://nodejs.org/)
- **PowerShell 7**: 推荐使用 PowerShell 7 以获得最佳命令支持。

### 1.1 配置加速镜像 (推荐)

为了加快依赖安装速度，建议配置国内镜像源：

```powershell
# pip 配置阿里加速镜像
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com

# npm 配置淘宝加速镜像
npm config set registry https://registry.npmmirror.com
```

## 2. 前端构建 (Web)

1. 进入 `web` 目录：
   ```powershell
   cd web
   ```
2. 安装依赖：
   ```powershell
   npm install
   ```
3. 执行构建：
   ```powershell
   npm run build
   ```
   构建完成后，会在 `web/dist` 目录下生成静态文件。

## 3. 后端环境配置 (Server)

1. 进入项目根目录：
   ```powershell
   cd ..
   ```
2. 创建并激活 Python 虚拟环境：
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. 安装后端依赖：
   ```powershell
   pip install -r server/requirements.txt
   ```
4. 安装生产级 WSGI 服务器 (Waitress)：
   ```powershell
   pip install waitress
   ```

## 4. 系统配置

在项目根目录下编辑 `config.yaml` 文件，根据实际环境调整配置：

```yaml
SERVER_PORT: 5000               # 服务端口
DB_PATH: "data/database.db"     # 数据库存放路径
CACHE_DIR: "data/cache"         # 缩略图缓存存放路径
LOG_LEVEL: "INFO"               # 日志级别 (DEBUG, INFO, ERROR)
ANONYMOUS_ACCESS: true          # 是否允许匿名访问
THUMBNAIL_QUALITY: 80           # 缩略图质量 (1-100)
SCAN_RECURSIVE: true            # 是否递归扫描文件夹
SCAN_EXTENSIONS: ".jpg,.jpeg,.png,.gif,.bmp,.webp,.tiff"
```

**注意**：确保 `data` 目录及其子目录对运行程序的用户具有读写权限。

## 5. 启动服务

### 5.1 生产环境运行 (推荐)

在生产环境下，不建议使用 Flask 自带的开发服务器。建议编写一个简单的启动脚本 `prod_run.py`：

```python
import os
import sys
from waitress import serve

# 确保在项目根目录下运行
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# 将 server 目录添加到 Python 路径，以便 'from app import ...' 能够工作
sys.path.insert(0, os.path.join(project_root, 'server'))

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = app.config.get('SERVER_PORT', 5000)
    print(f"Starting production server on http://localhost:{port}")
    serve(app, host='0.0.0.0', port=port)
```

运行启动脚本：
```powershell
python prod_run.py
```

### 5.2 作为 Windows 服务运行

可以使用 `NSSM` (Non-Sucking Service Manager) 将程序注册为 Windows 服务，实现开机自启和后台运行。

1. 下载 [NSSM](https://nssm.cc/download)。
2. 执行命令安装服务：
   ```powershell
   nssm install PictureWeb
   ```
3. 在弹出的窗口中配置：
   - **Path**: `D:\Workspace\PicGallery\venv\Scripts\python.exe`
   - **Startup directory**: `D:\Workspace\PicGallery`
   - **Arguments**: `prod_run.py`

## 6. 维护与备份

- **日志查看**：系统运行日志将根据 `LOG_LEVEL` 输出到终端或配置的日志文件中。
- **数据库备份**：定期备份 `data/database.db` 文件。
- **缓存清理**：如果磁盘空间不足，可以安全删除 `data/cache` 目录下的内容，系统会在需要时重新生成。

## 7. 常见问题 (FAQ)

- **端口冲突**：如果 5000 端口被占用，请在 `config.yaml` 中修改 `SERVER_PORT`。
- **路径问题**：确保 `DB_PATH` 和 `CACHE_DIR` 使用相对路径或合法的 Windows 绝对路径。
- **权限不足**：运行 PowerShell 时建议使用管理员权限，特别是在执行扫描任务或删除操作时。
