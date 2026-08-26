# BioDB 测试实例部署总结（技术性）

> 本文档总结 BioDB（生体数据仓库）测试实例的部署过程与部署架构。
> 资料依据：`biodb-main/`（源码包 `biodb-main.zip`）中的 `README.md`、`compose.yaml`、`.env.example`、各 `Dockerfile`、`nginx/nginx.conf`、`postgresql/01-schema.sql`、`docs/biodb-spec.md` 等。
> 状态：测试实例部署（本地/单机 Docker Compose）。

---

## 1. 概要

| 项目 | 内容 |
|---|---|
| 系统 | BioDB：生体数据仓库（传感器时序列 + 事件 + 用户权限） |
| 部署方式 | Docker Compose 单机编排（`compose.yaml`） |
| 外部入口 | NGINX，`http://localhost:5002/` |
| WebUI | `/WebUI/`（SvelteKit SSG 静态构建，NGINX 分发） |
| API 路由 | `/auth`（认证）、`/sensor`（传感器）、`/event`（事件） |
| 数据存储 | VictoriaMetrics（时序列）、MongoDB（事件/长期 Token）、PostgreSQL（用户/权限） |

架构原则：**外部仅暴露 NGINX 端口，API 与 DB 均在 Compose 内部网络通过服务名解析**，不创建外部网络。

---

## 2. 系统架构

```
                        ┌─────────────────────────────┐
  Client ── :5002 ────▶ │  nginx (nginx:1.27-alpine)  │
                        │  ├─ /WebUI/  → 静态文件      │
                        │  ├─ /auth/   → auth:8000     │
                        │  ├─ /sensor/ → sensor:8001   │
                        │  └─ /event/  → event:8002    │
                        └─────────────────────────────┘
                                  │ (Compose 内部网络)
        ┌───────────┬─────────────┼──────────────┬──────────────┐
        ▼           ▼             ▼              ▼              ▼
   ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌───────────┐   ┌────────────┐
   │  auth   │ │ sensor  │ │  event    │ │ admin*    │   │ WebUI 构建 │
   │ :8000   │ │ :8001   │ │  :8002    │ │ (one-shot)│   │ node:22    │
   │ Flask   │ │ FastAPI │ │  Flask    │ │  uv run   │   │ (多阶段)   │
   └────┬────┘ └────┬────┘ └─────┬─────┘ └─────┬──────┘   └────────────┘
        │           │           │             │
        ▼           ▼           ▼             ▼
   ┌─────────┐ ┌──────────┐ ┌─────────┐  ┌──────────┐
   │postgres │ │ victoria │ │  mongo  │  │  DB 数据 │
   │ 17.2    │ │ v1.116.0 │ │  7.0.16 │  │ 挂载卷   │
   │+pg_cron │ │          │ │         │  │(repo 下) │
   └─────────┘ └──────────┘ └─────────┘  └──────────┘
```

*`admin` 属于 `tools` profile，正常启动不包含，用于一次性创建初始管理员。*

---

## 3. 基础设施组件

### 3.1 PostgreSQL（用户 / 权限）
- 镜像：`postgres:17.2`（自建 Dockerfile 追加 `postgresql-17-cron` 扩展）。
- 启动参数：`shared_preload_libraries=pg_cron`、`cron.database_name=postgres`。
- 凭据（compose.yaml 固定）：用户 `soma` / 密码 `testtest` / 库 `biodb`。
- Schema：`01-schema.sql` 仅创建 `biodbapi` schema（`AUTHORIZATION soma`），表结构由 SQLAlchemy 启动时自动建表。
- 数据卷：`./postgresql/db_vol:/var/lib/postgresql/data`。

### 3.2 MongoDB（长期 Token / 事件数据）
- 镜像：`mongo:7.0.16`（无自定义构建）。
- 凭据：root / `testtest`（`MONGO_INITDB_ROOT_USERNAME/PASSWORD`）。
- 数据卷：`./mongodb/data/configdb`、`./mongodb/data/db`。

### 3.3 VictoriaMetrics（传感器时序列数据）
- 镜像：`victoriametrics/victoria-metrics:v1.116.0`。
- 启动参数：`-storageDataPath=/storage`、`-retentionPeriod=100y`（保留 100 年，面向研究数据长期保存）。
- 数据卷：`./victoria_metrics/vm_data:/storage`。
- API 路径约定（由 API 服务使用）：`http://victoria:8428`，写入 `/write`，导出 `/api/v1/export`，基础指标名 `biodb`。

> 注：原设计曾采用 InfluxDB，因大量请求时出现 stall 而迁移至 VictoriaMetrics。

---

## 4. API 服务（Python，Gunicorn 托管）

公共构建参数（YAML 锚点 `x-api`）：所有 API 容器均 `env_file: .env` 并注入数据库连接环境变量。

### 4.1 auth（认证授权服务器）
| 项 | 值 |
|---|---|
| 构建 | `bio_api_server/Dockerfile.auth`（python:3.11-slim） |
| 入口 | `main:app`，Gunicorn `-w 4 -b 0.0.0.0:8000` |
| 依赖 | postgres、mongo |
| 职责 | 长期 Token 创建/管理、用户信息 API、被测者（participant）管理、JWT 发行 |
| 包含模块 | `main.py`、`env.py`、`psql.py`、`ptoken.py`、`pvalid.py`、`create_admin.py`、`templates/index.html` |

### 4.2 sensor（生体数据 API）
| 项 | 值 |
|---|---|
| 构建 | `bio_api_server/Dockerfile.sensor_victoria` |
| 入口 | `sensor_server:app`，Gunicorn + `uvicorn.workers.UvicornWorker`，`-w 12 -b 0.0.0.0:8001 --timeout 180 --keep-alive 60` |
| 依赖 | victoria |
| 职责 | 传感器数据的读写（高频写入，多 worker + 异步 worker 适配） |
| 包含模块 | `victoria_sensor_server.py`（构建时复制为 `sensor_server.py`）、`env.py`、`pvalid.py`、`p_victoria_metrics.py` |

### 4.3 event（事件数据 API）
| 项 | 值 |
|---|---|
| 构建 | `bio_api_server/Dockerfile.event` |
| 入口 | `event_server:app`，Gunicorn `-w 2 -b 0.0.0.0:8002` |
| 依赖 | mongo |
| 职责 | 事件数据的基本 CRUD（创建/获取/删除/更新） |
| 包含模块 | `event_server.py`、`env.py`、`pvalid.py`、`pevent.py` |

### 4.4 admin（一次性管理员创建，tools profile）
- 构建：`Dockerfile.admin`，基础镜像 `python:3.11-slim` + `uv`（ghcr.io/astral-sh/uv:0.10.7）。
- 执行：`uv run --with nanoid==2.0.0 --with SQLAlchemy==2.0.36 --with psycopg2-binary==2.9.10 --with python-dotenv==1.0.1 python create_admin.py`。
- 说明：不随正常启动运行；通过 `docker compose --profile tools run --rm admin --email <mail>` 调用。

依赖版本要点（`requirements.txt`）：Flask 3.1.0、Flask-JWT-Extended 4.7.1、FastAPI 0.115.12、gunicorn 23.0.0、uvicorn 0.34.2、SQLAlchemy 2.0.36、pymongo 4.10.1、psycopg2-binary 2.9.10、google-auth 2.37.0、flasgger 0.9.7b2 等。

---

## 5. WebUI 与反向代理

### 5.1 WebUI（`bio_svelte/`，SvelteKit）
- 框架：Svelte 5 + SvelteKit 2.16 + Vite 6.2，`adapter-static`（SSG）。
- 构建阶段：多阶段 Dockerfile 中 `node:22-alpine` 执行 `npm ci && npm run build`，产物为静态文件。
- 页面：登录、用户信息、被测者管理（列表/新增/编辑）、长期 Token 列表/创建。
- 构建期注入：`PUBLIC_GOOGLE_CLIENT_ID`（来自 `.env` 的 `GOOGLE_CLIENT_ID`，为必填构建参数）。

### 5.2 NGINX（`nginx/nginx.conf`）
- 镜像：`nginx:1.27-alpine`；`worker_connections 1024`。
- 静态：`/WebUI/` 映射至 `/usr/share/nginx/html/WebUI`，SPA fallback 到 `index.html`。
- 路由（内部代理 + 保留 Host / X-Real-IP / X-Forwarded-* 头）：
  - `/auth/` → `http://auth:8000/`
  - `/sensor/` → `http://sensor:8001/`
  - `/event/` → `http://event:8002/`
  - 各服务的 Swagger 资源 `/auth|sensor|event/apidocs`、`apispec_1.json`、`flasgger_static/` 一并代理。
- 对外端口：`5002:80`。

---

## 6. 配置与环境变量

### 6.1 `.env`（仅 3 个值，由 `.env.example` 复制而来）
```bash
APP_SECRET_KEY=replace-with-a-random-value        # 生成: python -c "import secrets; print(secrets.token_urlsafe(32))"
APP_JWT_SECRET_KEY=replace-with-a-random-value    # 生成方式同上
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
```
- 用途：应用会话密钥、JWT 签名密钥、Google OAuth Client ID（认证与 WebUI 构建共用）。
- DB 连接信息**不写入 `.env`**，固定于 `compose.yaml`（测试实例默认值：`soma/testtest` 等）。

### 6.2 环境变量注入（compose.yaml `x-api` 锚点）
`POSTGRES_USER/PASSWORD/HOST/PORT`、`MONGO_USER/PASSWORD/HOST/PORT`、`VICTORIA_METRICS_HOST/EXPORT_PATH/WRITE_PATH/BASE_METRIC_NAME`，以及 `env.py` 预留的 Redis、Influx 相关变量（当前 compose 未启用）。

---

## 7. 部署步骤（测试实例实操）

前置条件：Docker + Docker Compose。

```bash
# 1) 准备环境变量（密钥用 secrets.token_urlsafe(32) 生成）
cp .env.example .env
#   编辑 .env: APP_SECRET_KEY / APP_JWT_SECRET_KEY / GOOGLE_CLIENT_ID

# 2) 构建并后台启动全部服务（首次构建较慢：npm ci + pip install）
docker compose up --build -d

# 3) 注册初始管理员（Google 登录前必须先在 DB 登记邮箱）
docker compose --profile tools run --rm admin --email user@example.com

# 4) 验证
#    WebUI : http://localhost:5002/WebUI/
#    Swagger: http://localhost:5002/auth/apidocs
#             http://localhost:5002/sensor/apidocs
#             http://localhost:5002/event/apidocs
```

服务状态检查：`docker compose ps`；日志：`docker compose logs -f <service>`。

---

## 8. 认证与数据写入流程（客户端视角）

BioDB 采用 **长期 Token（认证）+ 短命 JWT（授权）** 双令牌机制，`/sensor`、`/event` 的大多数 API 需要 JWT。

```python
import requests

# 1) 用 user_id + 长期 token 换取写权限 JWT（权限不同端点不同）
resp = requests.post(
    f"{SERVER_URL}/auth/jwt/sensors/writejwt",
    json={"user_id": USER_ID, "token": TOKEN,
          "participant_id": PARTICIPANT_ID,
          "start_time": ..., "end_time": ...},
)
jwt = resp.json()["jwt"]

# 2) JWT 放入 Authorization 头调用业务 API
requests.post(f"{SERVER_URL}/sensor/data/write",
              json=body,
              headers={"Authorization": f"Bearer {jwt}"})
```

要点：
- JWT 内含有效期（设置较短），过期后需重新获取。
- 秘密密钥仅服务器持有，客户端无法伪造/校验。

---

## 9. 数据持久化与初始化

| 数据 | 宿主目录（repo 下，需纳入备份） |
|---|---|
| PostgreSQL | `./postgresql/db_vol` |
| MongoDB | `./mongodb/data/`（configdb + db） |
| VictoriaMetrics | `./victoria_metrics/vm_data` |

- 完全重置：停止服务后删除或移走上述目录，再 `docker compose up -d`（PostgreSQL 会重新执行 `01-schema.sql`）。
- 初始化流程：首次启动时 PostgreSQL 自动执行 `/docker-entrypoint-initdb.d/01-schema.sql`；业务表由 SQLAlchemy 建表；管理员通过 admin 容器创建。

---

## 10. 运维注意事项

1. **密钥安全**：`.env` 中的 `APP_SECRET_KEY` / `APP_JWT_SECRET_KEY` 必须替换为随机值，禁止默认值上生产。
2. **Google OAuth**：`GOOGLE_CLIENT_ID` 为必填（compose 构建参数），缺失会导致 nginx 构建失败。
3. **端口**：对外仅 5002；如需修改，同步调整 `compose.yaml` 的 `ports`。
4. **健康检查**：Compose 未显式配置 healthcheck，依赖 `depends_on` 启动顺序；sensor 服务 worker 数较高（12）且超时较长（180s），适配高频批量写入。
5. **数据保留**：VictoriaMetrics `retentionPeriod=100y`，注意磁盘容量规划。
6. **升级路径**：修改镜像 tag 后 `docker compose up -d --build`，同时备份数据目录。

---

## 11. 与 PhysioFlow 平台的集成展望

按项目路线图（`README.md` / `docs`），BioDB 作为数据仓库承接 PhysioFlow（PF）实验流程采集的生体数据：
- 识别体系：PF 的 `protocolId` + participant → BioDB 的 `experiment` + `participant` 标签（二段识别）。
- 下一步：BioDB 增加 `experiment` 维度 → PF 侧提供 BioDB 数据管理面板 → 分析/可视化。
- 测试实例即本部署实例，作为集成联调与验收的环境。

---

## 12. 实际部署记录（2026-08-26，本机 Windows + Docker Desktop）

### 12.1 环境与前置条件
- OS：Windows 11，Docker Desktop（WSL2 后端）。
- **关键前置**：CPU 虚拟化（Intel VT-x）必须在 BIOS/UEFI 中开启，否则 Docker Desktop / WSL2 无法启动（报 `virtualisation support wasn't detected`）。i5-14600K 默认支持，需在 BIOS 的 `Advanced → CPU Configuration → Intel Virtualization Technology` 中启用。
- `.env`：按 `.env.example` 创建，`APP_SECRET_KEY` / `APP_JWT_SECRET_KEY` 用 `secrets.token_urlsafe(32)` 生成；`GOOGLE_CLIENT_ID` 暂用占位值（Google 登录不可用，其余功能不受影响）。

### 12.2 构建与启动
```bash
cd biodb-main
docker compose up --build -d          # 首次构建约 5-15 分钟（npm ci + pip install）
docker compose --profile tools run --rm admin --email <邮箱>   # 创建初始管理员
```

### 12.3 部署中遇到的问题与修复

**问题 1：auth 容器启动时崩溃（Connection refused）**
- 现象：`auth` 容器反复 `Restarting`，日志显示 `psycopg2.OperationalError: connection to server at "postgres" ... Connection refused`。
- 根因：`depends_on` 仅保证容器启动顺序，不等待 PostgreSQL 就绪；首次启动时 postgres 需初始化（建库、装 pg_cron、执行 `01-schema.sql`），期间 `auth` 启动阶段的 SQLAlchemy 建表连接被拒。
- 处理：无需人工干预，`restart: unless-stopped` 策略在 postgres 就绪后自动拉起成功。

**问题 2：flasgger Swagger UI 重定向丢失端口/前缀**
- 现象：`GET /auth/apidocs`（无尾斜杠）返回 308，`Location: http://localhost/auth/apidocs/`（端口丢失，浏览器跳转到 80 端口失败）；修复过程中还出现过 `http://localhost:5002/apidocs/`（前缀丢失）。
- 根因：flask strict_slashes 对 `/apidocs` 生成 308；后端基于 Host 头生成绝对 URL，而 nginx `proxy_pass http://auth:8000/` 剥离了 `/auth/` 前缀且 flasgger 无法感知外部端口。
- 修复（nginx.conf，3 个 API 前缀 location 通用）：
  ```nginx
  # 无尾斜杠的 Swagger 入口直接规范化重定向（保留端口与前缀）
  location = /auth/apidocs { return 308 $scheme://$http_host/auth/apidocs/; }
  # 转发时透传原始 Host（含端口）与代理头
  location /auth/ {
      proxy_pass http://auth:8000/;
      proxy_set_header Host $http_host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_redirect / /auth/;
  }
  ```
- 注意：`return 308 /auth/apidocs/`（相对路径）会被 nginx 基于 `$host` 生成绝对 Location 而丢端口，必须显式用 `$scheme://$http_host` 构造。

### 12.4 验证结果（冒烟测试）
| 检查项 | 结果 |
|---|---|
| `docker compose ps` | 7/7 容器 `Up` |
| `http://localhost:5002/WebUI/` | 200（SvelteKit 静态页面） |
| `http://localhost:5002/auth/apidocs` | 200（重定向至 `/auth/apidocs/`） |
| `http://localhost:5002/sensor/docs` | 200（FastAPI Swagger UI） |
| `http://localhost:5002/event/apidocs` | 200 |
| `POST /auth/jwt/sensors/writejwt`（无效 token） | 400 `Token is invalid`（认证链路正常） |
| admin 容器创建管理员 | 成功（`users` 表写入，role=admin） |
| PostgreSQL `biodbapi` schema | 已建 `users`、`participants` 表 |

### 12.5 后续事项
- 将 `.env` 的 `GOOGLE_CLIENT_ID` 替换为真实值后，执行 `docker compose up -d --build nginx`，即可启用 Google 登录。
- 数据目录（`postgresql/db_vol`、`mongodb/data`、`victoria_metrics/vm_data`）在 repo 内，纳入备份与版本控制规划。

### 12.6 管理员邮箱更换（2026-08-26）
- 现象：WebUI 点击 Google 登录时报 `The OAuth client was not found`——根因是 `.env` 中 `GOOGLE_CLIENT_ID` 仍为占位值（`your-google-oauth-client-id.apps.googleusercontent.com`），该 Client ID 在 Google Cloud 不存在，与管理员账号无关。
- 操作：将占位管理员 `admin@example.com` 替换为真实 Google 账号 `dhtr87852@gmail.com`：
  ```bash
  docker compose --profile tools run --rm admin --email dhtr87852@gmail.com
  # 输出: New admin user 'dhtr87852@gmail.com' has been created. ID: sYLepkQgUlFdtpRkp3rYo
  docker exec biodb-main-postgres-1 psql -U soma -d biodb -c "DELETE FROM biodbapi.users WHERE email = 'admin@example.com';"
  ```
- 验证：`biodbapi.users` 现仅 1 行 `dhtr87852@gmail.com / admin`；`/auth/apidocs`、`/sensor/docs`、`/event/apidocs` 均 200。
- 完成：Google Cloud Console 已创建 OAuth 2.0 Web Client（应用类型=网页应用，授权 JavaScript 来源=`http://localhost:5002`，重定向 URI 留空——WebUI 使用 GIS 弹窗模式 `data-ux_mode="popup"`，不依赖 redirect URI）。真实 Client ID 已写入 `.env` 并重建 `nginx` + `auth`，验证 WebUI 静态产物与 auth 环境变量均已注入新 ID。登录流程为浏览器端 GIS 获取 ID token → `POST /auth/google/callback`（`id_token.verify_oauth2_token` 校验，无需 Client Secret）。

### 12.7 D1 实施：experiment tag 二段识别（2026-08-26）
- 需求：`04-d1-experiment-tag.md`（P0，时序数据加 `experiment` 维度，形成 experiment + participant 二段识别）。
- 改动（4 文件，纯增量，向后兼容）：
  - `pvalid.py`：`GetJwtSensorsRequestBody` / `GetJwtEventsRequestBody` / `GetJwtServiceRequestBody` 新增可选 `experiment_id`。
  - `main.py`：5 个 JWT 签发点（sensors writejwt/readjwt、events、service readjwt/events）在 `additional_claim` 条件性注入 `experiment`（仅当请求提供 `experiment_id` 时）。
  - `victoria_sensor_server.py`：写入端从 JWT claims 取 `experiment`，注入 `data_df["experiment"]` 并条件性加入 `tag_columns`；读回端将 `experiment_id_val` 传入导出函数。
  - `p_victoria_metrics.py`：`victoria_metrics_export_and_format_data` 新增 `experiment_id_val: Optional[str] = None`，构造 VM selector 时条件性追加 `experiment="..."`。
- 验收（同一 participant `7C64JubjmS5mpecsFkBTU`，两次实验各写 EDA 一条）：
  - 写入 `experiment=exp_emotion`（eda=1.1）与 `experiment=exp_cognition`（eda=9.9）均 200。
  - VM `/api/v1/series` 确认两个独立 series：`biodb_eda{experiment="exp_emotion"}`、`biodb_eda{experiment="exp_cognition"}`。
  - 按实验读回：`exp_emotion` → `eda=[1.1]`；`exp_cognition` → `eda=[9.9]`，隔离正确 ✅。
  - 已知行为：不带 experiment 读回时同名 metric（`biodb_eda`）多个 series 在输出 JSON 中 key 相同、同时间戳互相覆盖（既有格式化逻辑 `format_vm_data_with_original_metric_names` 所致）。业务上始终按 experiment 查询即可规避；如需无过滤并集输出，需将该函数输出 key 扩展为含 experiment（后续优化项）。
- 排障记录：重建 `auth`/`sensor` 后 nginx 502——nginx 启动时缓存了上游容器旧 IP，需 `docker compose restart nginx` 重新解析。
- 测试数据清理：测试长期 token（`description='D1 acceptance test'`）已从 MongoDB `auth_database.tokens` 删除；测试 participant 与 VM 演示数据保留。

### 12.8 事件与实验关联（2026-08-26，02-gap §3.6 / P1）
- 需求：BioDB event 原仅有 `user_id`（协作者），缺 event ↔ experiment 关联。本次为事件增加可选 `experiment_id` 字段，事件可按实验组织、查询、隔离。
- 改动（3 文件，纯增量，向后兼容）：
  - `pvalid.py`：`EventDataCreateRequestBody` / `EventData` / `EventDateUpdatePostBody` 新增可选 `experiment_id`。
  - `pevent.py`：`create_event` 新增 `experiment_id` 参数；`get_events` 新增 `experiment_id` 过滤。
  - `event_server.py`：
    - 创建事件：`experiment` 归属以 JWT claim 优先（R2 不可伪造）——JWT 带 claim 时强制使用；请求体值若与 claim 不一致返回 400 `Invalid request body`；JWT 无 claim 时允许请求体指定（向后兼容）。
    - 查询事件：`GET /event/events` 新增可选 query 参数 `experiment_id`。
    - 更新事件：更新 `experiment_id` 时须与 JWT claim 一致，否则 400。
- 验收（participant `7C64JubjmS5mpecsFkBTU`）：
  - 创建 `exp_emotion` 事件 `stimulus_on` 与 `exp_cognition` 事件 `trial_start` 均 200。
  - 按实验过滤查询：`experiment_id=exp_emotion` → 仅 `stimulus_on@exp_emotion`；`exp_cognition` → 仅 `trial_start@exp_cognition`；`exp_other` → 空 ✅。
  - R2 不可伪造：用 `exp_emotion` 的 event JWT 提交 `experiment_id=exp_cognition` → 400 `Invalid request body` ✅。
  - 向后兼容：不带 experiment 的旧 JWT 创建事件仍 200（`experiment_id=null`）✅。
- 测试数据清理：事件验收 token 已删除；演示事件保留于 MongoDB `event_database.events`。

### 12.9 实验元数据注册表 + 数据字典 + 无过滤读回并集（2026-08-26，02-gap §3.2/§3.3 + D1 遗留）
- 需求：三项补齐
  1. **实验元数据**（02-gap §3.2）：experiment 仅有 tag 值，无注册表/元数据 → 新增注册表 + CRUD API。
  2. **数据字典对接**（02-gap §3.3，D4）：缺「时序通道 → 数据字典」→ 实验文档内嵌 `dictionary`（通道名 → label/unit/type 等）并提供存取 API。
  3. **无过滤读回并集**（D1 遗留）：无过滤读回时同名 metric 同时间戳互相覆盖 → 输出 key 附加 `@<experiment>` 后缀。
- 改动（4 文件，纯增量，向后兼容）：
  - `pexperiment.py`（新增）：MongoDB `event_database.experiments` 集合操作层（`create_experiment` / `get_experiment_by_id` / `get_experiments` / `update_experiment` / `delete_experiment` / `get_experiment_dictionary` / `update_experiment_dictionary`）；`experiment_id` 可指定或自动生成 UUID，`name` 唯一（对应时序/事件写入的 experiment 标签值）。
  - `pvalid.py`：新增 `ExperimentCreateRequestBody` / `ExperimentUpdateRequestBody` / `ExperimentDictionaryUpdateRequestBody`。
  - `main.py`：新增 7 个管理端点（WebUI JWT + `userRole=admin` 鉴权，复用 create_user 模式），挂载于 auth 服务，对外路径 `/auth/...`：
    - `POST /experiment`（创建）、`GET /experiments`（列表）、`GET /experiment/<id>`（详情）、`POST /experiment/<id>`（更新）、`DELETE /experiment/<id>`（删除）、`GET /experiment/<id>/dictionary`（字典读取）、`POST /experiment/<id>/dictionary`（字典整体替换）。
  - `p_victoria_metrics.py`：`format_vm_data_with_original_metric_names` 统计本次读回涉及的 experiment 集合——多个不同 experiment 时输出 key 为 `{column}@{experiment}`；单一 experiment（含按实验过滤读回）保持原 key。
  - `Dockerfile.auth`：COPY 清单新增 `pexperiment.py`。
- 验收（admin `dhtr87852@gmail.com`，participant `7C64JubjmS5mpecsFkBTU`，数据 `exp_emotion eda=1.1` / `exp_cognition eda=9.9`）：
  - 实验 CRUD：创建 exp_emotion（含 dictionary）与 exp_cognition 均 200；重名创建/重名更新 → 400；列表/详情/更新/删除 200；删除后查询 404；非 admin JWT → 400 `Jwt Error` ✅。
  - 数据字典：创建时内嵌 `{"eda":{"label":"皮肤电","unit":"uS"},...}`；`POST /experiment/<id>/dictionary` 整体替换 → 200；`GET` 读回一致 ✅。
  - 无过滤读回：`rows=["eda"]` 无 experiment claim → `keys=["time","eda@exp_emotion","eda@exp_cognition"]`，值 `1.1`/`9.9` 不再互相覆盖 ✅。
  - 过滤读回（向后兼容）：claim `experiment=exp_emotion` → `keys=["time","eda"]`，`eda=[1.1]`；`exp_cognition` → `eda=[9.9]` ✅。
- 验证注意：sensor 读回按 `CHUNK_DURATION_SECONDS=5` 分片遍历请求时间范围，验证时须用窄时间窗（本次用 2026-08-25~27），避免大范围读回产生数百万次 export 请求。

### 12.10 时序采集质量统计（2026-08-26，02-gap 数据模型缺口「时序缺失/质量问题」）
- 需求：时序数据无采集质量元数据（丢帧率、时间戳连续性）→ 新增读回侧质量统计端点，即算即查、不落库。
- 改动（2 文件，纯增量）：
  - `p_victoria_metrics.py`：新增 `compute_data_quality_stats(result_json)`——基于读回格式化结果，对每个数据列计算 `points`/`total_points`/`completeness`（完整率）、`min`/`max`/`mean`/`median`/`std`、`interval_ms`（相邻实际样本间隔 min/max/median/mean）、`max_gap_seconds`（最大间隔，秒）、`expected_points`/`estimated_missing_rate`（以中位间隔为期望采样间隔的缺失率估计）；辅助函数 `_parse_vm_time_ms` / `_format_vm_time`。
  - `victoria_sensor_server.py`：新增 `POST /data/quality` 端点（FastAPI），鉴权与 `/data/read` 完全一致（`sensor_read` 角色、时间窗校验、experiment claim 过滤），内部复用 `victoria_metrics_export_and_format_data` 读回后计算质量，直接返回 JSON（不经压缩信封）。
- 验收（admin `dhtr87852@gmail.com` 生成 JWT）：
  - 连续 100Hz/10s 写入 1000 点 → `points=1000`、`interval_ms={min:10,max:10,median:10}`、`max_gap_seconds=0.01`、`estimated_missing_rate=0.0` ✅。
  - 两段间隔 5s（各 20 点 @100ms）→ `total_points=40`、`interval_ms={min:100,max:3100,median:100}`、`max_gap_seconds=3.1`、`expected_points=70`、`estimated_missing_rate=0.4286`（40/70）✅。
  - 现有单点（exp_emotion eda=1.1）→ `points=1`、`interval_ms=null`（不足 2 点不可算间隔）✅。
  - 无数据实验 → `total_points=0` ✅；`sensor_write` 角色调用 → 403 `Unauthorized role` ✅。
- 验证注意：写入后立即查询偶见返回空（VM 索引短暂延迟），稍候重查即正常；大时间窗 + 5s chunk 遍历较慢，建议窄窗查询。

### 12.11 六项功能端到端验收（2026-08-26）

#### 12.11.1 验收范围与测试环境

| 项 | 内容 |
|---|---|
| 验收对象 | ① 48h 窗口动态分片读回 `/sensor/data/read`；② 联合导出 `/sensor/data/export`（sensor 数据 + 事件 + 实验元数据）；③ 特征统计 `/sensor/data/features`（时域 + 频域）；④ ML 分析（`/sensor/analysis/train/kmeans`、`train/regression`、`predict`、`GET/DELETE analysis/results`）；⑤ util 可视化页面 `/util/`；⑥ 文档更新 |
| 测试账号 | admin `dhtr87852@gmail.com`（user_id `sYLepkQgUlFdtpRkp3rYo`） |
| 测试 participant | `7C64JubjmS5mpecsFkBTU` |
| 时间窗 | `2026-08-25T00:00:00` ~ `2026-08-27T00:00:00`（48h） |
| 访问方式 | 经 NGINX `http://localhost:5002`；维多利亚容器无主机端口映射，容器内脚本经 `http://victoria:8428` 直查 |
| JWT | `POST /auth/jwt/sensors/{readjwt,writejwt}` 获取；**短有效期，过期后需重新生成**（曾因 exp 过期导致 400） |

测试数据：`tools/write_test_data.py`（`docker cp` 入 sensor 容器 `/tmp/` 运行）写入 100Hz 仿真 EDA/PPG 信号，起始 `2026-08-26T10:10:00`，时间戳固定输出 6 位微秒。

#### 12.11.2 发现并修复的 Bug（3 个真实 Bug + 1 个测试脚本问题）

**Bug A：大数据量读回全部 400 → 读回为空（时间格式）**
- 现象：48h 窗动态分片遍历时，分片起止时间由 `datetime.isoformat()` 生成，微秒非 0 时产生**无时区 + 小数秒**字符串（如 `2026-08-25T00:01:26.400000`），维多利亚 `/api/v1/export` 无法解析 → 全部 400 → 聚合结果为空（此前误判为「无数据」）。
- 修复（`bio_api_server/p_victoria_metrics.py`）：新增 `_to_vm_iso(dt)`，无时区时间补 UTC、统一 `astimezone(timezone.utc).isoformat()`，分片循环内起止时间一律经它转换。
- 复验：48h 窗读回 3300 点、耗时 378ms ✅

**Bug B：KMeans 训练报错——`label_distribution` 整数键被 MongoDB 拒绝**
- 现象：训练保存结果时 `pymongo` 报错（BSON 不支持整型数字键 dict）。
- 修复（`bio_api_server/pml.py`）：`label_distribution()` 返回键转字符串 `{str(int(k)): int(c)}`；train 与 predict 端点共用该函数，一并修复。

**Bug C（测试脚本，非生产代码）**：`tools/write_test_data.py` 原 `strftime("%Y-%m-%dT%H:%M:%S")` 把 100ms 间隔截断到秒，维多利亚按秒去重后读回仅剩 300 点；改为固定 6 位微秒后恢复 3300 点。

#### 12.11.3 各项验收结果

| # | 功能 | 结果 |
|---|---|---|
| 1 | 48h 动态分片读回 | ✅ 3300 点、378ms（修复 Bug A 后） |
| 2 | 联合导出 `/data/export` | ✅ 完全通过：注册 `exp_emotion_verify` 实验与事件后复验，sensor（eda/ppg 各 6000 点）+ 事件（1 条）+ 实验元数据（含数据字典）三部分齐全（见 12.11.5） |
| 3 | 特征统计 `/data/features` | ✅ 频域主频 0.1Hz 与 10s 周期模拟信号一致，推算采样率 10Hz；多点数据下频域特征正确 |
| 4 | ML 分析 | ✅ KMeans（3300 样本 3 簇，修复 Bug B）、回归训练（r2≈0 符合随机数据预期）、预测、结果列表、删除（含 owner 权限校验）均通过 |
| 5 | util 可视化页面 `/util/` | ✅ `history.html`、`realtime.html`、`event-chart.html`、`emotion-map.html`、`common.js`、`style.css` 全部 200（NGINX 静态分发） |
| 6 | 文档更新 | ✅ 本文档 |

#### 12.11.4 遗留事项
- JWT 有效期较短（10 分钟），长时间验证需重新获取；长期 token 可经 `tmp_create_token.py`（auth 容器内运行，scope=all、30 天）生成。
- 实验元数据联合导出已复验通过（见 12.11.5），测试环境注册表记录为验证而建，接入真实数据后以真实实验复验即可。
- 无过滤读回同名 metric 并集行为见 12.9（key 附 `@<experiment>` 后缀）。

#### 12.11.5 联合导出实验元数据补全复验（2026-08-26）
12.11 验收时第 2 项导出中的实验元数据为 null（注册表无记录），本次补全注册与事件后复验通过。

**步骤**
1. 实验注册记录：`event_database.experiments` 插入 `exp_emotion_verify`（label/description + 数据字典 `{eda, ppg}`）。注：注册表 CRUD 管理端点（12.9 实现）的创建需 admin WebUI JWT（Google OAuth），测试环境以直插 MongoDB 模拟「管理员已注册」；本次验证重点是导出端点正确读取注册表并打包。
2. 事件：`event_database.events` 插入 `evt_verify_001`（participant `7C64JubjmS5mpecsFkBTU`、11:00:10~11:00:20Z、`experiment_id=exp_emotion_verify`）。
3. 带 experiment 标签写入：`POST /auth/jwt/sensors/writejwt`（body 含 `experiment_id`，JWT 携带 `experiment` claim）→ `POST /sensor/data/write` 写入 100Hz×60s=6000 点（起始 2026-08-26T11:00:00，naive 固定 6 位微秒时间戳）。
4. 导出：`POST /sensor/data/export`（`rows=[eda,ppg]`、`11:00:00~11:01:00`、`include_events=true`、`include_experiment=true`）。

**结果**：sensor.eda / sensor.ppg 各 6000 点、events 1 条、experiment 非 null（含 `dictionary`）→ **PASS**。
- 注意：写后立即导出 sensor 为 0 点（维多利亚索引延迟），约 5s 后重试即全量返回（与 12.10 已知现象一致）。
- 可复跑脚本：`biodb-main/tools/verify_export.py`（宿主机 Python 3.11 标准库；需先重新获取带 `experiment` 的 write/read JWT 存入 `%TEMP%\biodb_write_jwt.txt` / `%TEMP%\biodb_jwt.txt`）。

#### 12.11.6 util 可视化页面读数据修复 + 时区使用注意（2026-08-26）
**Bug D：util 页面「JWT Secret Key Error」→ 读不到数据**
- 现象：`/util/history.html` 等页面读取数据时报 400 "JWT Secret Key Error"。
- 根因：后端 `decode_jwt`（`victoria_sensor_server.py`）严格要求 `Authorization: Bearer <jwt>`，前缀缺失时统一返回 400 "JWT Secret Key Error"；而 `bio_util/common.js` 的 readData/exportData/features 与 `history.html` 的 quality 请求只传 JWT 本体、漏掉 `Bearer ` 前缀（共 4 处）。
- 修复：4 处 `Authorization: jwt` → `Authorization: "Bearer " + jwt`；`docker cp` 同步 nginx 容器 `/usr/share/nginx/html/util/`。**浏览器需强刷（Ctrl+F5）避免旧缓存**。
- 复验：带 `Z` 时间戳 + `Bearer` 前缀经 `/sensor/data/read` 端到端通过（eda/ppg 各 6000 点）。

**时区使用注意（重要）**
- 数据时间戳按 **UTC** 存储（写入时 naive 字符串被维多利亚按 UTC 处理）；util 页面 `common.js` 的 `parseTimeInput` 将表单本地时间经 `toISOString()` 转 UTC 后查询。
- 因此表单需填**本地时间**，换算关系：本地 = UTC + 时区偏移。本验证环境为**东九区（UTC+9）**：查 `exp_emotion_verify`（UTC 11:00~11:01）填本地 `20:00~20:01`；查无标签数据（UTC 10:00~10:15）填本地 `19:00~19:15`。
- 排查工具：`biodb-main/tools/query_sensor_data.py`（内置长期 token，`--start/--end` 按 **UTC** 填，可快速确认某窗是否有数据）。

