---
alwaysApply: false
description: 当时涉及到项目目录结构、项目开发调试、项目技术栈规则、编写脚本，测试文件，文档时调用
---
# 全局规则

1.  如非必需场景，UI 界面、代码注释、日志输出使用简体中文。
    
2.  如非特别说明，默认使用前后端分离技术。
    
3.  开发环境为 Windows 环境。
    
4.  如非特别说明，前端页面使用响应式设计（比如 Bootstrap、Tailwind CSS），适配各类屏幕。
    
5.  项目目录规则如下：
    
    1.  /docs: 存放项目各类文档，并需要对文档进行分类，比如原型设计、开发文档、测试文档、部署文档等，按文件夹分类。
        
    2.  /data：存放项目必要的数据，比如数据库文件等。
        
    3.  /server：存放后端服务代码。
        
    4.  /web：存放 Web 前端代码。
        
    5.  /scripts：存放开发过程中的各类脚本，比如部署脚本，数据库脚本，测试脚本等，按文件夹分类。
        
    6.  /build：存放构建后的产物，包括 Web 构建物、Android 和 iOS 应用、Windows 客户端等，按文件夹分类。
        
    7.  /android：对于跨平台项目，存放安卓端代码。
        
    8.  /ios：对于跨平台项目，存放 iOS 代码。
        
    9.  /windows：对于跨平台项目，存放 Windows 端代码。
        

6.  python 项目开发调试过程使用 venv 虚拟环境，python 命令在虚拟环境中运行。
    
7.  python、node 项目开发环境使用热加载模式，改动代码后不用重启服务。
    
8.  前端统一定义和使用全局字体、字体大小，覆盖各组件自由的字体大小。
    
9.  系统已安装 chrome、edge、Firefox 浏览器可用于前端调试。
    

# 技术栈规则

1.  使用 Vue3 + Vite7（前端） + Python（后端） 构建项目。
    
2.  前端使用响应式布局。
    
3.  弹窗使用 element-plus 插件
    
4.  深色模式使用 Naive UI 或 element-plus
    
5.  数据库使用sqlite3本地存储

6.  后端使用Flask框架
    

# 开发调试规则

1. 不需要一步完成所有功能的开发，按照需求文档或技术文档进行分步规划，每次完成一部分功能并测试通过后继续下一步。
2. 对于需求文档或技术文档中指明的功能，严格按照文档说明开发，请勿改变功能实现。
3. 前端如果有原型设计，请按照原型设计设开发前端页面，并将系统功能绑定到前端。
4. 当前开发环境为 Windows，需要使用 Powershell 7 和其支持的相关命令。
5. npm 和 pip 使用加速镜像。
    
    ```shell
    # pip配置加速阿里加速镜像
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
    pip config set global.trusted-host mirrors.aliyun.com
    
    # npm配置淘宝加速镜像
    npm config set registry https://registry.npmmirror.com
    ```