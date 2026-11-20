# 个人知识管理平台

一个笔记 + 标签管理的 RESTful 后端服务。支持笔记的增删改查、置顶与归档、关键词搜索、标签筛选，以及标签维度的笔记计数。

**FastAPI + SQLAlchemy 2.0（异步）+ MySQL 8 + Alembic**，全异步实现。

> 学习项目，按周迭代。当前进度：第 10 周（数据模型 + 接口层完成），第 11 周补充 JWT 鉴权。

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
```

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

统一前缀无版本号，所有接口的 `user_id` 由服务端注入（当前为固定值，第 11 周替换为 JWT 解析）。

| 方法 | 路径 | 说明 | 成功状态码 |
|---|---|---|---|
| POST | `/notes` | 创建笔记（笔记与标签关联在同一事务内） | 201 |
| GET | `/notes` | 笔记列表，支持分页 / 关键词 / 标签筛选 | 200 |
| GET | `/notes/{note_id}` | 笔记详情 | 200 |
| PATCH | `/notes/{note_id}` | 局部更新，只改传入的字段 | 200 |
| PUT | `/notes/{note_id}/tags` | 标签整体替换 | 200 |
| DELETE | `/notes/{note_id}` | 删除笔记 | 204 |
| GET | `/tags` | 标签列表 + 每个标签关联的笔记数 | 200 |
| GET | `/health` | 健康检查 | 200 |

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
├── main.py                  # FastAPI 入口，挂载 api_router + /health
├── alembic.ini
├── alembic/
│   ├── env.py               # 异步迁移环境
│   └── versions/
├── app/
│   ├── config.py            # pydantic-settings 读取 .env
│   ├── database.py          # engine / AsyncSessionFactory / Base / get_db
│   ├── dependencies.py      # get_current_user_id（第 11 周替换为 JWT）
│   ├── schemas.py           # 全部 Pydantic 模型
│   ├── services.py          # 可复用的业务函数（get_or_create_tags）
│   ├── models/              # users / notes / tags / note_tags
│   └── routers/
│       ├── __init__.py      # api_router 汇总各子路由
│       ├── notes.py
│       └── tags.py
└── .env                     # 不提交
```

---

## 设计决策

这一节记录的是"为什么这样写"，每条都是权衡后的选择。

### 1. 认证尚未实现，但隔离逻辑已就位

`app/dependencies.py` 里的 `get_current_user_id()` 当前固定返回 `1`，所有接口通过
`Depends` 注入它。第 11 周接入 JWT 时，只需改这一个函数的实现，**所有接口的租户隔离逻辑一行都不用动**。

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

---

## 已知局限

| 局限 | 影响 | 后续方案 |
|---|---|---|
| `LIKE '%kw%'` 前缀通配，索引失效 | 数据量大后搜索全表扫描 | 引入全文索引 / 搜索引擎 |
| `OFFSET` 深分页越翻越慢 | 第 1000 页需扫描前 2 万行 | 换游标分页（`WHERE id < 上一页最后一条 id`） |
| `DATETIME` 精度为秒 | 同一秒内更新的笔记排序不稳定 | 排序加 `id DESC` 兜底；或字段改 `DATETIME(6)` |
| 孤儿标签不回收 | 清空标签后 `tags` 表留下零引用记录 | 由 `GET /tags` 暴露 + 定期清理任务 |
| 无用户认证 | 所有请求以固定用户身份执行 | 第 11 周接入 JWT |
| 无自动化测试 | 回归靠手工 curl | 补 pytest + httpx 集成测试 |

---

## 路线图

- [x] 第 10 周：数据模型、迁移、六个 CRUD 接口 + 标签计数
- [ ] 第 11 周：用户注册 / 登录、bcrypt 密码哈希、JWT 鉴权，替换 `get_current_user_id`
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
