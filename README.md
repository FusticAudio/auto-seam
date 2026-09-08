# auto-seam

基于 **DXF 裁片图** 的服装缝制关系自动标注与可视化预览工具集。

本仓库围绕一条完整工作流运行：`auto-annotator` 是一个独立完整的 Web 应用（含 DXF 上传界面与 FastAPI 自动标注后端），将工程裁片 DXF 自动解析为「裁片（garment）+ 缝合关系（seam）」两份 JSON；`seam-preview` 则是一个独立的轻量前端工具，加载这两份 JSON 进行可视化预览与人工校对。

```
auto-seam/
├── auto-annotator/   # 独立 Web 应用：DXF 上传界面 + FastAPI 自动标注后端 → garment / seam JSON
└── seam-preview/     # 轻量前端工具：缝合关系预览、人工缝合编辑、JSON 重新保存（纯单页 HTML）
```

---

## 一、项目概述

### auto-annotator —— DXF 自动缝合关系标注

一个独立完整的 Web 应用，由 **DXF 上传前端界面** 与基于 **FastAPI** 的 **自动标注后端** 两部分组成。通过网页上传 `.dxf` 工程文件，后端自动解析出服装裁片及其间的缝合关系，返回两份标准 JSON（`*.garment.reviewed.json` 与 `*.seam.reviewed.json`），供下游 3D 执行器与预览工具使用。

- **输入**：`.dxf` 裁片工程图（含裁片名称 `Piece Name`、层信息、几何图元）
- **输出**：裁片 JSON（面板、实例、裁片说明）+ 缝合关系 JSON（缝合线、类型）
- **核心能力**：裁片检测、角色识别、边沿邻接、几何匹配、跨家族缝合校验、伪裁片过滤

### seam-preview —— 缝合关系预览与人工编辑

一个独立、零依赖的轻量前端工具，以纯单 HTML 页面（`seam-preview/index.html`）加载 `garment` 与 `seam` 两份 JSON，在 SVG 画布上还原裁片与缝合关系。

- **预览**：叠加显示裁片轮廓、裁片名称标签、缝合关系连线，支持缩放、平移、适合画布
- **人工缝合**：通过框选边沿，人工建立 / 修改缝合关系（source:manual）
- **保存**：将修改后的缝合关系重新序列化并下载为 JSON，实现「自动生成 → 人工校对 → 重新保存」闭环

---

## 二、环境配置指南

### 1. Python（仅 auto-annotator 需要）

- 建议版本：**Python 3.10 ~ 3.11**（已在 3.11 环境下验证）
- 依赖遵循 `auto-annotator/requirements.txt`：

| 依赖              | 版本要求 | 用途             |
| ----------------- | -------- | ---------------- |
| fastapi           | >= 0.110 | Web 服务框架     |
| uvicorn[standard] | >= 0.29  | ASGI 服务器      |
| python-multipart  | >= 0.0.9 | 支持文件上传表单 |
| ezdxf             | >= 1.3   | DXF 文件解析     |

### 2. seam-preview

**无需安装任何依赖**，仅需现代浏览器（Chrome / Firefox / Edge），可直接打开 HTML 文件运行。

### 3. 安装步骤（auto-annotator）

```bash
cd auto-annotator

# 方式一：使用 venv（推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 可选：安装环境文件示例（本项目当前不读环境变量，详见"环境文件"章节）
# Copy-Item .env.example .env   # PowerShell
# cp .env.example .env          # bash
```

> 说明：本项目的 FastAPI 服务当前不依赖任何自定义环境变量，`HOST` / `PORT` 直接通过 uvicorn 命令行参数传入即可，`.env` 仅为可选的统一放置入口（见后续章节）。

### 环境文件（.env）使用说明

仓库附带环境模板 `auto-annotator/.env.example`，定义了以下预留变量：

| 变量         | 作用                                                     | 示例值      |
| ------------ | -------------------------------------------------------- | ----------- |
| `HOST`       | 服务监听地址；`127.0.0.1` 仅本机，`0.0.0.0` 局域网可访问 | `127.0.0.1` |
| `PORT`       | 服务监听端口                                             | `8010`      |
| `RELOAD`     | 是否开启开发热重载模块                                   | `false`     |
| `API_PREFIX` | API 路由前缀                                             | `/api`      |

使用方法：

```bash
cd auto-annotator
# Windows (PowerShell)
Copy-Item .env.example .env
# Linux / macOS (bash)
cp .env.example .env
```

- 修改 `.env` 中的值即可覆盖对应运行参数。
- `.env` 属于本地敏感/个人配置，已被 `.gitignore` 忽略，**不会提交到仓库**；`!.env.example` 例外保留模板本身。
- 当前服务启动仍以 uvicorn 命令行参数为准（见「项目启动说明」），`.env` 是为启动脚本 / 后续版本预留的统一配置入口。

---

## 三、项目启动说明

### 启动 auto-annotator 服务

在 `auto-annotator` 目录下执行：

```bash
# Windows（激活 venv 后）
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8010
```

| 参数       | 说明                                 | 默认        |
| ---------- | ------------------------------------ | ----------- |
| `--host`   | 监听地址，`0.0.0.0` 表示局域网可访问 | `127.0.0.1` |
| `--port`   | 服务端口                             | `8000`      |
| `--reload` | 开发模式：代码变更自动重启           | 关          |

常用启动方式：

```bash
# 仅本机访问
.venv\Scripts\python -m uvicorn app.main:app

# 局域网可访问 + 开发热重载
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# 后台运行（产物写入日志）
Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8010" -NoNewWindow -RedirectStandardOutput out.log
```

启动后：

- **Web 上传界面**：`http://localhost:8010/`（由 `app/static` 挂载的前端页面）
- **标注 API**：`POST http://localhost:8010/api/annotate`（上传 `.dxf`，返回两份 JSON）

> 注意：uvicorn 未加 `--reload` 时**不会热重载**代码，修改后端逻辑后需重启服务。

### 启动 seam-preview

```bash
# 方式一：直接双击打开
start seam-preview\index.html

# 方式二：局域网共享预览（任意静态服务器，例如 npx http-server 或 python）
cd seam-preview
python -m http.server 8080
# 浏览器访问 http://localhost:8080/index.html
```

---

## 四、工作流程示例

### 1. 完整工作流

1. **准备 DXF**：备好一张包含裁片名称的工程裁片图（`.dxf`）。
2. **自动标注**：启动 auto-annotator，在 `http://localhost:8010/` 上传 DXF，下载生成的 `*.garment.reviewed.json` 与 `*.seam.reviewed.json`。
3. **预览核对**：打开 `seam-preview/index.html`，通过「批量加载」或分别「加载 Garment JSON / 加载 Seam JSON」载入两份文件。
4. **人工编辑**：开启「人工缝合」工具，框选边沿自动扩选，A/B 两侧确认后建立或删除缝合关系。
5. **重新保存**：点击「保存 Seam JSON」，将校对后的缝合关系下载为新 JSON，供 3D 执行器使用。

### 2. API 调用示例（curl）

```bash
curl -X POST http://localhost:8010/api/annotate \
     -F "file=@你的裁片.dxf"
```

返回一个 JSON 对象，包含 `garment` 与 `seam` 两套数据（或由前端直接触发下载）。

---

## 五、项目结构速览

```
auto-annotator/
├── app/
│   ├── main.py            # FastAPI 入口与 /api/annotate 接口
│   ├── core/
│   │   ├── parse.py       # DXF 图元解析与归属
│   │   ├── panels.py      # 裁片检测与拓扑
│   │   ├── geometry.py    # 几何算法（邻接 / 镜像 / 重叠）
│   │   ├── semantics.py   # 角色识别与语义规则
│   │   ├── schema.py      # garment / seam JSON 结构定义
│   │   └── service.py     # 业务编排与日志
│   └── static/index.html  # 上传前端页面
├── requirements.txt
├── docs/                  # 设计 / 修复说明文档
└── outputs/               # 示例输出（reviewed JSON）

seam-preview/
└── index.html             # 单文件预览 + 人工缝合工具
```

---

## 六、许可与说明

- 本仓库面向服装 DXF 裁片自动化标注场景，输出 JSON 供 3D 执行器与预览工具消费。
- `outputs/` 内含若干示例成衣的 reviewed JSON，可作为格式参考与回归测试样本。

如有问题，请先查看 `auto-annotator/docs/` 与 `auto-annotator/outputs/` 中的示例产物。
