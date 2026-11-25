# 个人知识管理平台

一个笔记 + 标签管理的 RESTful 后端服务。支持笔记的增删改查、置顶与归档、关键词搜索、标签筛选，以及标签维度的笔记计数。

**FastAPI + SQLAlchemy 2.0（异步）+ MySQL 8 + Alembic**，全异步实现。

> 学习项目，按周迭代。当前进度：第 11 周完成（数据模型 + 全部 CRUD 接口 + 用户注册/登录 + JWT 鉴权 + 统一错误响应）。

---

## 技术栈

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.13 | |
| FastAPI | 0.163 | 路由、依赖注入、`response_model` 出参校验 |
| SQLAlchemy | 2.1 | `Mapped[]` 声明式模型 + `AsyncSession` |
| aiomysql | 0.3 | MySQL 异步驱动 |
| Pydantic | 2.14 | 入参/出参模型、字段校验 |
| pydantic-settings | 2.16 | `.env` 配置加载 |
| Alembic | 1.20 | 数据库迁移（异步 `env.py`） |
| MySQL | 8.0 | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| cryptography | 50.0 | MySQL 8 `caching_sha2_password` 认证必需 |
| bcrypt | 5.0 | 密码哈希，`gensalt(12)` |
| PyJWT | 2.15 | 签发 / 校验 JWT（包名 `PyJWT`，import 写 `jwt`） |
| python-multipart | 0.0.34 | `OAuth2PasswordRequestForm` 解析 form 表单必需 |

> `cryptography` 不是可选项。MySQL 8 默认认证方式在非 TLS 连接下需要 RSA 加密，缺少它会报
> `RuntimeError: 'cryptography' package is required for caching_sha2_password auth methods`。

---

## 快速开始

### 1. 准备数据库

```sql
CREATE DATABASE knowledge_management
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
```

### 2. 安装依赖

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

依赖清单见根目录 `requirements.txt`，只锁直接依赖，每项带注释说明用途。三个容易被误删的：

- `sqlalchemy[asyncio]` —— 裸 `sqlalchemy` 不带 greenlet，`create_async_engine` 会直接 ImportError
- `uvicorn[standard]` —— 裸 `uvicorn` 不带 watchfiles，`--reload` 不生效
- `cryptography` —— 不装则 MySQL 8 的 `caching_sha2_password` 认证失败

### 3. 配置环境变量

项目根目录新建 `.env`（已在 `.gitignore` 中）：

```
DATABASE_URL=mysql+aiomysql://root:your_password@127.0.0.1:3306/knowledge_management?charset=utf8mb4
SECRET_KEY=把下面生成的一串贴进来
```

`SECRET_KEY` 用于 JWT 签名，**没有默认值，缺失会直接启动失败**（`ValidationError: SECRET_KEY Field required`）。
生成方式：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

这串东西换掉后，所有已签发的 token 立刻失效——这是唯一的"强制所有人重新登录"手段。

### 4. 建表

```bash
alembic upgrade head
```

### 5. 启动

```bash
uvicorn main:app --reload
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

> `.env` 是相对**当前工作目录**查找的，必须从项目根启动。
> 若后续改为从其他目录启动或容器化，需把 `app/config.py` 里的 `env_file` 改成
> `Path(__file__).resolve().parent.parent / ".env"`。

---

## 接口一览

统一前缀无版本号。除 `/auth/*` 与 `/health` 外，**所有接口都要求 `Authorization: Bearer <token>`**，
`user_id` 由服务端从 JWT 解析后注入，不接受客户端传参。

| 方法 | 路径 | 说明 | 成功状态码 |
|---|---|---|---|
| POST | `/auth/register` | 用户注册，用户名唯一；重名返回 409 | 201 |
| POST | `/auth/login` | 登录，**form 提交**（`username` / `password`），返回 JWT | 200 |
| POST | `/notes` | 创建笔记（笔记与标签关联在同一事务内） | 201 |
| GET | `/notes` | 笔记列表，支持分页 / 关键词 / 标签筛选 | 200 |
| GET | `/notes/{note_id}` | 笔记详情 | 200 |
| PATCH | `/notes/{note_id}` | 局部更新，只改传入的字段 | 200 |
| PUT | `/notes/{note_id}/tags` | 标签整体替换 | 200 |
| DELETE | `/notes/{note_id}` | 删除笔记 | 204 |
| GET | `/tags` | 标签列表 + 每个标签关联的笔记数 | 200 |
| GET | `/health` | 健康检查 | 200 |

### 认证怎么用

登录接口收的是 **form**（`application/x-www-form-urlencoded`），不是 JSON：

```bash
TOKEN=$(curl -s --noproxy "*" -X POST http://127.0.0.1:8000/auth/login \
  -d "username=alice&password=yourpassword" \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s --noproxy "*" http://127.0.0.1:8000/notes -H "Authorization: Bearer $TOKEN"
```

> 用 JSON 打登录接口会得到 **422**，`loc` 指向 `body.username` —— 这是提交格式错了，不是字段名错了。

打开 `/docs` 点右上角 **Authorize** 可以直接用：填用户名密码，Swagger UI 会照着 `tokenUrl`
自己换 token。能这样是因为 `OAuth2PasswordBearer(tokenUrl="/auth/login")` 把登录地址告诉了文档页。

### `GET /notes` 查询参数

| 参数 | 类型 | 默认 | 约束 | 说明 |
|---|---|---|---|---|
| `keyword` | str | 无 | — | 标题或正文包含该词，`%` / `_` 会被转义 |
| `tag` | str | 无 | — | 按标签名筛选，大小写不敏感 |
| `page` | int | 1 | `>= 1` | 页码 |
| `size` | int | 20 | `1 ~ 100` | 每页条数 |

响应为分页包装：

```json
{
  "total": 4,
  "items": [
    {
      "id": 8,
      "title": "自填时间",
      "created_at": "2026-11-19T22:35:42",
      "updated_at": "2026-11-19T22:35:42",
      "is_pinned": false,
      "is_archived": false,
      "tags": ["Python"]
    }
  ]
}
```

排序固定为 `is_pinned DESC, updated_at DESC`。列表项不含 `content`，详情才返回全文。

### `GET /tags` 响应

```json
[
  { "name": "FastAPI", "note_count": 2 },
  { "name": "Python", "note_count": 1 }
]
```

`note_count` 只统计**未归档**的笔记，与 `GET /notes?tag=xxx` 返回的 `total` 严格一致。

### 错误响应

**成功响应不包信封**，直接返回资源本身；**HTTP 状态码就是契约**。错误侧统一成 `{"detail": "一句话"}`，
只有字段级校验失败（422）额外带一个 `errors` 数组。

| 场景 | 状态码 | 响应体 |
|---|---|---|
| 未知路由 / 方法不对 | 404 / 405 | `{"detail": "资源不存在"}` / `{"detail": "请求方法不允许"}` |
| 未带 token | 401 | `{"detail": "未认证，请先通过 /auth/login 换取 token"}` + `WWW-Authenticate: Bearer` |
| 业务错误（自己抛的） | 4xx | `{"detail": "笔记不存在"}`（原样透出，不进映射表） |
| 字段校验失败 | 422 | `{"detail": "请求参数校验失败", "errors": [{"field": "password", "msg": "..."}]}` |
| 未捕获异常 | 500 | `{"detail": "服务器内部错误"}`，堆栈只进服务端日志 |

422 的 `field` 是从 `loc` 拼出来的字段路径，嵌套结构用 `.` 连接（`tags.0` 表示 `tags` 数组第 0 项）；
body 整体不是合法 JSON 时 `field` 为 `"body"`。

`errors` 里**只有 `field` 和 `msg`**——pydantic 原始错误对象里的 `input`（用户提交的原文）和 `ctx`
（异常的原始对象）一律丢弃。前者会导致密码明文回显，后者不可 JSON 序列化。

---

## 数据模型

四张表，`users 1:N notes`、`users 1:N tags`、`notes M:N tags`（经 `note_tags`）。

```
users ──1:N──> notes ──┐
  │                    ├── note_tags ──> tags
  └────1:N─────────────┘                  │
                                          └── (UNIQUE user_id+name)
```

| 表 | 关键字段 | 备注 |
|---|---|---|
| `users` | `username` 唯一、`password_hash` | 密码存 bcrypt 哈希，绝不存明文 |
| `notes` | `user_id`(FK, 索引)、`title`、`content`(MEDIUMTEXT)、`created_at`、`updated_at`、`is_pinned`、`is_archived` | 外键 `ON DELETE CASCADE` |
| `tags` | `user_id`(FK)、`name` | 联合唯一 `UNIQUE(user_id, name)`；不另建 `user_id` 单列索引，靠联合索引最左前缀 |
| `note_tags` | `note_id` + `tag_id` 联合主键 | 两个外键均 `ON DELETE CASCADE`；`tag_id` 单独建索引以支撑按标签反查 |

---

## 目录结构

```
Knowledge_Management/
├── main.py                  # FastAPI 入口，注册异常处理器 + 挂载 api_router + /health
├── alembic.ini
├── alembic/
│   ├── env.py               # 异步迁移环境
│   └── versions/
├── app/
│   ├── config.py            # pydantic-settings 读取 .env
│   ├── database.py          # engine / AsyncSessionFactory / Base / get_db
│   ├── dependencies.py      # OAuth2PasswordBearer + get_current_user_id + get_owned_note
│   ├── exceptions.py        # 三个全局异常处理器 + register_exception_handlers(app)
│   ├── security.py          # bcrypt 哈希 / JWT 签发与解析（纯工具，不 import fastapi）
│   ├── schemas.py           # 全部 Pydantic 模型
│   ├── services.py          # 可复用的业务函数（get_or_create_tags）
│   ├── models/              # users / notes / tags / note_tags
│   └── routers/
│       ├── __init__.py      # api_router 汇总各子路由
│       ├── auth.py          # 注册 / 登录
│       ├── notes.py
│       └── tags.py
├── scripts/
│   └── test_api.py          # httpx 接口自测（22 条断言，需先启动服务）
└── .env                     # 不提交
```

---

## 设计决策

这一节记录的是"为什么这样写"，每条都是权衡后的选择。

### 1. user_id 走依赖注入，换鉴权方式时业务接口一行不用改

第 10 周所有接口就通过 `Depends(get_current_user_id)` 拿用户身份，那时函数体是写死的 `return 1`。
第 11 周接 JWT，只改 `dependencies.py` 里这一个函数的实现，**七个业务接口的代码一个字都没动**。

反过来如果让前端传 `?user_id=5`，等于任何人都能读别人的笔记。这一行是整个服务的安全底座。

### 2. 标签关联用"整体替换"，不是"追加"

`PUT /notes/{note_id}/tags` 的语义是"我给的列表就是最终结果"。幂等、可预测、支持清空（`"tags": []`）。

若用 POST 追加，用户取消一个标签就没有对应接口，还得再设计一套删除语义。

### 3. `PATCH` 里的 `tags` 走"三分法"

| 请求体 | 语义 |
|---|---|
| 没有 `tags` 字段 | 标签**不动** |
| `"tags": []` | **清空** |
| `"tags": ["a", "b"]` | **整体替换** |

靠 `pop("tags", None)` 之后 `None` 与 `[]` 的区分来表达这三种情况。

注意数组在这里是**替换**语义而非 PATCH 常见的合并语义——数组"合并"如何定义去重与顺序没有共识，约定成替换更稳定。

### 4. 改标签时必须手动刷新 `updated_at`

`updated_at` 的 `onupdate=datetime.now` 只在 `notes` 行真的发出 `UPDATE` 时触发。
只改标签时，变的是 `note_tags` 中间表，`notes` 行一列都没动，`onupdate` 不会执行。

后果很具体：列表按 `updated_at DESC` 排序，用户给笔记加完标签、刷新列表，这篇还在原位置。
所以在标签分支里显式写 `note.updated_at = datetime.now()`。

### 5. 拒绝软删除

软删（加 `is_deleted` 字段）看似安全，实际代价是**每一次查询都要记得过滤**，而 `db.get()` 无法附加条件——
现有四个接口都靠 `db.get(Note, note_id)` 取对象，加了软删后会静默返回已删除的笔记，必须全部改写。

另外 `is_archived` 已经存在，再加一个删除标记会让笔记有三个状态，语义边界不清。恢复功能属于回收站产品需求，不在本题范围内。

### 6. `total` 与 `items` 必须共用同一份 `conditions`

分页的 `total` 和列表查询用 `where(*conditions)` 展开同一个列表。
若两处条件不一致，就会出现"total 说有 5 条，翻页只有 3 条"的问题，而且页数少时根本看不出来。

两条语句因 Session 的 autobegin 落在同一事务、MySQL 默认 REPEATABLE READ 读同一快照，所以数字不会互相打架。
这也是**不需要**显式写 `async with db.begin()` 的原因——只读查询没有事务语义收益，还多一次 `COMMIT` 往返。

### 7. 标签筛选用 `EXISTS` 子查询，不用 `JOIN`

```python
Note.tags.any(Tag.name == tag)
```

生成 `EXISTS (...)`。若改成 `join(Note.tags).where(...)`，一篇笔记有几个匹配标签结果集就有几行，`count(*)` 会被放大。

### 8. `GET /tags` 用 `LEFT JOIN` + `count(Note.id)`

三处细节都有实测依据：

- **必须 `LEFT JOIN`**：零引用的标签也要出现在列表里（`note_count: 0`），`INNER JOIN` 会让它整条消失。
- **必须 `count(Note.id)` 而不是 `count(*)`**：`count(*)` 数的是结果行数，LEFT JOIN 产生的 (标签, NULL) 行会被算成 1，孤儿标签会显示成 1。
- **归档过滤必须写在 `ON` 里**，写在 `WHERE` 里会把 LEFT JOIN 降级成 INNER JOIN，零引用的标签又会被筛掉。

```python
.outerjoin(Note, and_(
    Note.id == NoteTag.note_id,
    Note.is_archived.is_(False),
    Note.user_id == user_id,
))
```

### 9. 关键词搜索用 `LIKE '%kw%'`，不用全文索引

`contains(keyword, autoescape=True)`，`autoescape` 会把用户输入里的 `%` 和 `_` 转义。
不加的话，搜索「100%」会变成 `LIKE '%100%%'`，匹配全表。

`relationship` 相关：`Note.tags` / `Tag.notes` 一组多对多关系，`lazy="selectin"` 避免异步下的懒加载异常，
不加 `cascade delete-orphan`——多对多的 `secondary` 表，SQLAlchemy 删除父对象时本来就会主动清理关联行，
数据库侧的 `ON DELETE CASCADE` 是第二道保险。

### 10. 统一用 404，不区分"不存在"和"不是你的"

"存在但无权访问"返回 403、"不存在"返回 404，攻击者能靠状态码差异枚举出哪些 `id` 真实存在。
统一返回 404，外部无法区分。这是安全惯例，不是偷懒。

### 11. 鉴权时不查库确认用户存在

`get_current_user_id()` 只解析 token，不 `db.get(User, user_id)`。代价是已删除用户的 token 在过期前仍能过鉴权，
但它的请求会全部因为 `Note.user_id == user_id` 过滤不到数据而返回空列表，不会越权。

换来的是每个请求省一次 SELECT——鉴权是**每个请求都要走**的路径，省在这里收益最大。
若将来需要"封禁即生效"，再引入黑名单或 `token_version` 字段。

### 12. 登录失败不区分"用户不存在"和"密码错误"

两种情况返回完全相同的 401 `{"detail": "用户名或密码错误"}`。分开说就等于送了一个用户名枚举接口。

判断写成 `if not user or not verify_password(...)` 也利用了短路求值：用户不存在时**不会**再跑一次 bcrypt，
既省掉约 200ms 的哈希开销，也避免响应时间泄露"这个用户名到底存不存在"。

### 13. 成功响应不包 `{code, msg, data}` 信封

国内教程常见的做法是把所有响应包成 `200 + {"code": 0, "message": "success", "data": {...}}`。本项目的取舍是**不做**：

- **HTTP 状态码本身就是统一格式。** 业务异常一律返回 200，等于关掉 `curl -f`、网关重试、监控告警、
  云平台健康检查这些所有读状态码的东西，上面的「成功状态码」表格也会立刻变成谎话
- **`response_model` 会废掉。** 包信封要写 `ApiResponse[NoteDetail]` 这类泛型，`/docs` 里每个接口两层套娃，
  看不到真实字段结构
- 唯一的收益是"前端只判 `code`"，而前端本来就要处理非 2xx 的响应，省不掉

统一的是**错误侧**，不是成功侧。

### 14. 422 丢弃 `input` 和 `ctx`

只保留 `field` 和 `msg`。两个键各有理由：

- `input` 是用户提交的原文——密码校验失败时它就是密码明文。今天只进响应，一旦第 13 周前端接了
  Sentry 之类的错误上报，密码就进了第三方日志
- `ctx` 里装着原始异常对象（`ctx: {"error": ValueError(...)}`）。**`JSONResponse` 不经过 `jsonable_encoder`**，
  直接塞进 `content` 会让 422 处理器自己炸成 500——正好发生在它最该工作的场景上

顺带解决可读性：前端不用再处理 `loc` 可能是 `["body","tags",0]` 这种带下标的形态。

### 15. 框架英文文案按 `detail` 映射，不按状态码覆盖

`FRAMEWORK_MESSAGES` 的键是文案（`"Not Found"` → `"资源不存在"`），不是状态码。

若按状态码写 `{404: "资源不存在"}`，会把接口自己抛的 `HTTPException(404, detail="笔记不存在")`
一并抹成笼统的四个字，比英文更糟。按文案查表就能区分"框架抛的"和"业务抛的"——后者不在表里，原样返回。

`"Not authenticated"` 要单独列一条：它是 `OAuth2PasswordBearer` 在 `auto_error=True` 时抛的，
不是状态码 401 对应的标准 phrase（那个是 `"Unauthorized"`）。

---

## 已知局限

| 局限 | 影响 | 后续方案 |
|---|---|---|
| `LIKE '%kw%'` 前缀通配，索引失效 | 数据量大后搜索全表扫描 | 引入全文索引 / 搜索引擎 |
| `OFFSET` 深分页越翻越慢 | 第 1000 页需扫描前 2 万行 | 换游标分页（`WHERE id < 上一页最后一条 id`） |
| `DATETIME` 精度为秒 | 同一秒内更新的笔记排序不稳定 | 排序加 `id DESC` 兜底；或字段改 `DATETIME(6)` |
| 孤儿标签不回收 | 清空标签后 `tags` 表留下零引用记录 | 由 `GET /tags` 暴露 + 定期清理任务 |
| 测试脚本留下固定残留 | `scripts/test_api.py` 每次跑完，`zz_api_user` 账号连同名下 `zz_test` / `FastAPI` 两条零引用标签常驻 `users` / `tags` 表 | 脚本按名字 `get_or_create` 复用已有标签，**ID 不会持续增长**（固定为 27 / 28）；彻底清理需业务层标签回收，不值得为测试数据加 |
| 测试脚本不是 pytest | 22 条断言靠 `print` 输出，无 fixture、参数化、用例隔离 | 第 12 周后视需要迁移到 pytest |
| 跨用户越权没有回归断言 | 脚本只用单一账号跑 happy path，隔离逻辑改坏了照样 22/22（已实测验证过这一点） | 补第二个账号，断言详情/改/删/换标签全 404，列表与搜索结果为空 |
| token 签发后无法主动失效 | 退出登录或改密码后，旧 token 在 60 分钟内仍有效 | 加黑名单（存 Redis）或短期 access + refresh token 双 token |
| 500 的响应体是固定文案 | 客户端看到的信息量为零，定位问题只能翻服务端日志 | 需要时在响应里带 `trace_id`，与日志关联 |
| `/health` 不返回版本信息 | 服务跑的是旧代码时探活照样返回 200，测试脚本分辨不出来 | `/health` 带上 commit hash 或启动时间 |

---

## 路线图

- [x] 第 10 周：数据模型、迁移、六个 CRUD 接口 + 标签计数
- [x] 第 11 周：用户注册 / 登录、bcrypt 密码哈希、JWT 鉴权，替换 `get_current_user_id`；所有权校验抽成依赖；全局异常处理与统一错误响应
- [ ] 第 12 周：Dockerfile + docker-compose（MySQL + 应用），注意显式安装 `cryptography`
- [ ] 第 13 周：Streamlit 前端

---

## 开发备注

- **不要用 `TestClient` 测异步 ORM 接口**：每个请求新建事件循环，连接池错乱、请求交替 500。
  起真实 `uvicorn` 再用 `httpx` 或 `curl` 打。
- 启动后想确认路由是否注册成功，打印 `app.openapi()['paths']`，比翻代码快。
  FastAPI 0.163 下 `app.routes` 里看到的是 `_IncludedRouter`，不可靠。
- 一次性脚本结尾要 `await engine.dispose()`，否则 Windows 上会刷
  `RuntimeError: Event loop is closed`（aiomysql 连接对象 GC 时触发）。uvicorn 下不会出现。
- 异步 ORM 必须设 `expire_on_commit=False`，否则 commit 后再读属性会抛 `MissingGreenlet`。
- `scripts/test_api.py` 的**退出码约定**：`0` = 22 条全过；`1` = 有用例失败，或服务根本没启动。
  脚本开头先探 `/health`，分两段判断：`try/except httpx.TransportError` 管传输层（连不上、超时），
  紧跟 `if r.status_code != 200` 管应用层（连上了但服务状态不对）。只看前者会漏掉"路由丢了但端口还通"的情况。
  所以它可以直接接在 `&&` 链后面或丢进 CI。
- 验退出码时**别接管道**：`python x.py | tail` 之后 `$?` 取的是 `tail` 的状态，永远是 0。
  要么先 `> log 2>&1` 再 `echo $?`，要么 `set -o pipefail`。
- **PyJWT 2.x 校验 `sub` 必须是字符串**：`jwt.encode({"sub": 1})` 能编码成功，但 `decode` 时会抛
  `InvalidSubjectError`。签发时写 `str(user_id)`，解析时再 `int(payload["sub"])`。
- `jwt.decode(..., algorithms=[...])` 的列表**不能省**：省掉等于接受 token 自称的任何算法。
- 所有 decode 失败（过期、签名错、格式错、`sub` 非字符串）都继承 `jwt.InvalidTokenError`，
  一个 `except` 就能全接住；但要额外带上 `KeyError`（无 `sub`）和 `ValueError`（`sub` 不是数字）。
- 密码上限是 **72 字节**（不是 72 字符）：bcrypt 5.x 对超长输入直接抛 `ValueError`，不是静默截断。
  一个汉字占 3 字节，所以 24 个汉字就已经到顶了——校验必须按 `len(v.encode("utf-8"))` 算。
- `Exception` 的处理器挂在最外层 `ServerErrorMiddleware` 上，响应发出后**异常会重新抛一遍**
  （`starlette/middleware/errors.py` 里的 `raise exc`）。所以加了 handler 之后控制台照样打完整 traceback，
  这不是没生效，而是设计如此：日志归日志，响应归响应。
  但 `FastAPI(debug=True)` 会让这个处理器**彻底失效**，改用 HTML 调试页并把源码片段暴露给浏览器——别为了看堆栈开它。
- **`JSONResponse` 不经过 `jsonable_encoder`**。`request_model`/`response_model` 那条路会自动转 `datetime`、
  异常对象等，`JSONResponse(content=...)` 不会，塞进去就是 `TypeError: Object of type X is not JSON serializable`。
  所以 422 处理器要主动丢弃 `ctx`（内含 `ValueError` 实例），而不是靠 encoder 兜底。
- 异常处理器里**不要碰 `db`**：异常可能正发生在事务中间，session 状态未知，再查一次只会套出第二个异常，
  客户端收到的是 `Exception in ASGI application`，连 500 的 JSON 都没了。
