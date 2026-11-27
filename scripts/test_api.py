import asyncio
import time

import httpx

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("√" if ok else "×") + name)
    if not ok and detail:
        print(detail)


async def main():
    created_ids = []
    note_id = None
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", trust_env=False) as client:
        # 先探活，服务没起就别往下跑了
        try:
            r = await client.get("/health")
        except httpx.TransportError as e:
            print(f"服务没起来（{type(e).__name__}）：先在项目根执行 uvicorn main:app --reload")
            raise SystemExit(1)
        if r.status_code != 200:
            print(f"/health 返回 {r.status_code}，服务没正常起来：{r.text[:80]}")
            raise SystemExit(1)
        # ---- 新增：先测鉴权，此时 client 还没 token ----
        r = await client.get("/notes")
        check("无 token 返回 401", r.status_code == 401, r.text[:60])

        # ---- 新增：注册（幂等）+ 登录拿 token ----
        await client.post("/auth/register", json={"username": "zz_api_user", "password": "TestPass123"})
        r = await client.post("/auth/login", data={"username": "zz_api_user", "password": "TestPass123"})
        check("登录拿到 token", r.status_code == 200 and "access_token" in r.json(), r.text[:100])
        if r.status_code == 200:
            client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        try:
            r = await client.post("/notes", json={
                "title": "zz测试笔记",
                "content": "随便写点东西",
                "tags": ["zz_test"],
            })
            check("POST 返回 201", r.status_code == 201, r.text[:100])
            if r.status_code == 201:
                body = r.json()
                note_id = body["id"]
                created_ids.append(note_id)
                check("标题与请求一致", body["title"] == "zz测试笔记", body["title"])
                check("标签与请求一致", body["tags"] == ["zz_test"], body["tags"])
            r = await client.post("/notes", json={"title": "", "content": "×"})
            check("空标题返回422", r.status_code == 422, r.text[:100])
            r = await client.get("/notes")
            check("列表返回 200", r.status_code == 200, r.text[:100])
            body = r.json()
            check("total 是整数", isinstance(body["total"], int), body.get("total"))
            if note_id is not None:
                check("列表包含刚建的笔记", any(item["id"] == note_id for item in body["items"]))
            r = await client.get("/notes", params={"keyword": "zz测试"})
            body = r.json()
            check("搜索有结果", body["total"] >= 1, body["total"])
            check("结果都含关键词", all("zz测试" in (i["title"] + i.get("content", "")) for i in body["items"]))
            r = await client.get("/notes", params={"keyword": "%"})
            body = r.json()
            check("total==0", body["total"] == 0)
            r = await client.get("/notes", params={"tag": "zz_test"})
            body = r.json()
            check("total>=1", body["total"] >= 1)
            r = await client.get(f"/notes/{note_id}")
            body = r.json()
            check("详情返回 200 且含 content", r.status_code == 200 and "content" in body, r.text[:100])
            r = await client.get("/notes/999999")
            check("错误返回404", r.status_code == 404)
            #下面都属于PATCH /notes/{id} {"title": "zz改过的标题"}
            r = await client.get(f"/notes/{note_id}")
            old_body = r.json()
            old_time = old_body["updated_at"]
            old_title = old_body["title"]
            await asyncio.sleep(1.1)
            r = await client.patch(f"/notes/{note_id}", json={"title": "zz改过的标题"})
            body = r.json()
            update_title = body["title"]
            update_time = body["updated_at"]
            check("标题与 updated_at 均已更新",
                  update_title != old_title and update_time != old_time,
                  f"{old_time} → {update_time}")
            #--------------------------------------------------
            r = await client.patch(f"/notes/{note_id}", json={"content": None})
            body = r.json()
            check("content 没被 null 清空",
                  r.status_code == 200 and body["content"] == "随便写点东西",
                  repr(body.get("content")))
            r = await client.patch("/notes/999999", json={"title": "×"})
            check("错误，返回404", r.status_code == 404)
            r = await client.put(f"/notes/{note_id}/tags", json={"tags": ["FastAPI"]})
            body = r.json()
            check("tags变成FastAPI", r.status_code == 200 and body["tags"] == ["FastAPI"])
            r = await client.put(f"/notes/{note_id}/tags", json={})
            check("未传参数，错误，返回422", r.status_code == 422)
            r = await client.delete(f"/notes/{note_id}")
            check("删除成功，不返回内容", r.status_code == 204 and r.text == "")
            if r.status_code == 204:
                created_ids.remove(note_id)
            r = await client.delete(f"/notes/{note_id}")
            check("未找到此id的笔记", r.status_code == 404)

            # ============ 鉴权与参数边界：补覆盖率缺口的部分 ============
            # 1) 坏 token：形状像 Bearer，但解不开 → 401。
            #    这一条同时覆盖 dependencies.py 的 user_id is None 和 security.py 的 except
            r = await client.get("/notes", headers={"Authorization": "Bearer not-a-real-jwt"})
            check("坏 token 返回 401", r.status_code == 401, f"{r.status_code} {r.text[:80]}")
            check("坏 token 的 401 带 WWW-Authenticate",
                  r.headers.get("WWW-Authenticate") == "Bearer",
                  r.headers.get("WWW-Authenticate"))

            # 2) 用户名对、密码错 → 401（登录失败分支）
            r = await client.post("/auth/login",
                                  data={"username": "zz_api_user", "password": "wrong_password_123"})
            check("密码错误返回 401", r.status_code == 401, f"{r.status_code} {r.text[:80]}")

            # 3) 注册成功路径。固定用户名永远走 409，所以每次用时间戳造一个新的
            new_user = f"zz_api_reg_{int(time.time())}"
            r = await client.post("/auth/register",
                                  json={"username": new_user, "password": "TestPass123"})
            check("注册新用户返回 201", r.status_code == 201, f"{r.status_code} {r.text[:80]}")
            r = await client.post("/auth/register",
                                  json={"username": new_user, "password": "TestPass123"})
            check("重复注册返回 409", r.status_code == 409, f"{r.status_code} {r.text[:80]}")

            # 4) 25 个中文字 = 75 字节 > 72。Field 的 max_length 数的是字符，拦不住，靠 AfterValidator
            r = await client.post("/auth/register",
                                  json={"username": "zz_api_longpwd", "password": "密" * 25})
            errs = r.json().get("errors", []) if r.status_code == 422 else []
            check("超 72 字节的密码返回 422 且 field 是 password",
                  bool(errs) and errs[0].get("field") == "password",
                  f"{r.status_code} {r.text[:120]}")

            # 5) 非法 JSON：解析阶段就失败，loc 里没有字段名，field 只能是 body
            r = await client.post("/notes", content=b'{"title":',
                                  headers={"Content-Type": "application/json"})
            errs = r.json().get("errors", []) if r.status_code == 422 else []
            check("非法 JSON 返回 422 且 field 是 body",
                  bool(errs) and errs[0].get("field") == "body",
                  f"{r.status_code} {r.text[:120]}")

            # 6) PATCH 带 tags / 清空 tags。PUT /tags 测过了，但 PATCH 里是另一段代码
            r = await client.post("/notes", json={"title": "zz_patch_tags", "content": "x"})
            body = r.json()
            tag_note_id = None
            check("建一条专门测 PATCH tags 的笔记", r.status_code == 201, f"{r.status_code} {r.text[:80]}")
            if r.status_code == 201:
                tag_note_id = body["id"]
                created_ids.append(tag_note_id)
            if tag_note_id is not None:
                r = await client.patch(f"/notes/{tag_note_id}", json={"tags": ["zz_patched"]})
                body = r.json()
                check("PATCH 能改标签",
                      r.status_code == 200 and body.get("tags") == ["zz_patched"],
                      f"{r.status_code} {body.get('tags')}")
                r = await client.patch(f"/notes/{tag_note_id}", json={"tags": []})
                body = r.json()
                check("PATCH 传空列表能清空标签",
                      r.status_code == 200 and body.get("tags") == [],
                      f"{r.status_code} {body.get('tags')}")

            # 7) 从没出现过的标签名 → 走「新建 Tag」分支
            fresh = f"zz_new_{int(time.time())}"
            r = await client.post("/notes",
                                  json={"title": "zz_新标签", "content": "x", "tags": [fresh]})
            body = r.json()
            check("POST 全新标签名会自动创建",
                  r.status_code == 201 and body.get("tags") == [fresh],
                  f"{r.status_code} {body.get('tags')}")
            if r.status_code == 201:
                created_ids.append(body["id"])

            # 8) 上面那个 fresh 标签再传一次，换成大写：清洗阶段就该合并成一个，不会去数据库里查
            r = await client.post("/notes",
                                  json={"title": "zz_去重", "content": "x",
                                        "tags": [fresh, fresh.upper()]})
            body = r.json()
            check("同名不同大小写的标签只留一个",
                  r.status_code == 201 and len(body.get("tags") or []) == 1,
                  f"{r.status_code} {body.get('tags')}")
            if r.status_code == 201:
                created_ids.append(body["id"])
        finally:
            for i in created_ids:
                try:
                    r = await client.delete(f"/notes/{i}")
                    if r.status_code != 204:
                        print(f"[清理] 笔记 {i} 未删掉：{r.status_code} {r.text[:60]}")
                except Exception as e:
                    print(f"[清理] 笔记 {i} 请求失败：{type(e).__name__}: {e}")
    ok_count = sum(1 for r in results if r[1])
    print(f"\n通过 {ok_count}/{len(results)}")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name}: {detail}")
    if ok_count != len(results):
        raise SystemExit(1)


asyncio.run(main())
