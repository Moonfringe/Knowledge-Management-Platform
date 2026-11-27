"""越权（IDOR）测试：B 拿着完全合法的凭证，去操作 A 的资源，应该什么都拿不到。

A = 资源所有者（zz_api_user，现成账号）
B = 入侵者（zz_api_other，本脚本幂等注册）

跑之前先起服务（不要带 --reload，方便后面跑覆盖率）：
    uvicorn main:app
然后：
    python scripts/test_authz.py
"""

import asyncio

import httpx

BASE = "http://127.0.0.1:8000"
A_USER, A_PWD = "zz_api_user", "TestPass123"
B_USER, B_PWD = "zz_api_other", "TestPass123"

A_TITLE = "zz_A的靶子"
A_TAG = "zz_ta"
B_TITLE = "zz_B自己的"
B_TAG = "zz_tb"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("√ " if ok else "× ") + name)
    if not ok and detail:
        print("   " + detail)


def expect(name, actual, want):
    """一个条件一条断言。失败时自动拼出「期望 X，实际 Y」"""
    check(name, actual == want, f"期望 {want!r}，实际 {actual!r}")


async def login(client, username, password):
    r = await client.post("/auth/login", data={"username": username, "password": password})
    if r.status_code != 200:
        print(f"{username} 登录失败：{r.status_code} {r.text[:100]}")
        raise SystemExit(1)
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"


async def main():
    a_ids, b_ids = [], []
    async with httpx.AsyncClient(base_url=BASE, trust_env=False) as ca, \
            httpx.AsyncClient(base_url=BASE, trust_env=False) as cb:
        # 探活：服务没起就别往下跑，否则十几条断言全红会被误认成代码问题
        try:
            r = await ca.get("/health")
        except httpx.TransportError as e:
            print(f"服务没起来（{type(e).__name__}）：先在项目根执行 uvicorn main:app")
            raise SystemExit(1)
        if r.status_code != 200:
            print(f"/health 返回 {r.status_code}，服务没正常起来：{r.text[:80]}")
            raise SystemExit(1)

        # B 注册：幂等，已存在会返回 409，不看返回值
        await cb.post("/auth/register", json={"username": B_USER, "password": B_PWD})

        await login(ca, A_USER, A_PWD)
        await login(cb, B_USER, B_PWD)

        try:
            # A 建靶子；B 也建一条自己的，否则"看不到 A 的"和"B 本来就是空的"分不清
            r = await ca.post("/notes", json={"title": A_TITLE, "content": "A 的内容", "tags": [A_TAG]})
            assert r.status_code == 201, f"A 建靶子失败：{r.status_code} {r.text[:200]}"
            note_a = r.json()["id"]
            a_ids.append(note_a)

            r = await cb.post("/notes", json={"title": B_TITLE, "content": "B 的内容", "tags": [B_TAG]})
            assert r.status_code == 201, f"B 建笔记失败：{r.status_code} {r.text[:200]}"
            note_b = r.json()["id"]
            b_ids.append(note_b)

            # ---- 1. B 读 A 的笔记 ----
            r_b = await cb.get(f"/notes/{note_a}")
            r_none = await cb.get("/notes/999999")
            expect("B 读 A 的笔记返回 404", r_b.status_code, 404)
            # 两个 404 必须不可区分，否则攻击者能靠响应差异枚举出哪些 id 真实存在
            check(
                "越权 404 与不存在 404 不可区分",
                r_b.status_code == r_none.status_code and r_b.json() == r_none.json(),
                f"B 看 A 的：{r_b.status_code} {r_b.text[:80]}  |  "
                f"B 看不存在的：{r_none.status_code} {r_none.text[:80]}",
            )

            # ---- 2. B 改 A 的标题 ----
            r = await cb.patch(f"/notes/{note_a}", json={"title": "被B改了"})
            expect("B 改 A 的笔记返回 404", r.status_code, 404)
            # 404 只说明接口返回了 404，不说明数据没被污染，必须用 A 自己再读一遍
            after = (await ca.get(f"/notes/{note_a}")).json()
            expect("A 的标题没被 B 改动", after["title"], A_TITLE)

            # ---- 3. B 换 A 的标签 ----
            r = await cb.put(f"/notes/{note_a}/tags", json={"tags": ["hack"]})
            expect("B 换 A 的标签返回 404", r.status_code, 404)
            after = (await ca.get(f"/notes/{note_a}")).json()
            expect("A 的标签没被 B 改动", after["tags"], [A_TAG])

            # ---- 4. B 删 A 的笔记 ----
            r = await cb.delete(f"/notes/{note_a}")
            expect("B 删 A 的笔记返回 404", r.status_code, 404)
            r = await ca.get(f"/notes/{note_a}")
            expect("A 的笔记仍然存在", r.status_code, 200)

            # ---- 5. 列表过滤 ----
            r = await cb.get("/notes", params={"size": 100})
            ids = [i["id"] for i in r.json()["items"]]
            check("B 的列表不含 A 的笔记", note_a not in ids, f"实际 id 列表：{ids}")
            check("B 的列表含自己的笔记", note_b in ids, f"期望含 {note_b}，实际：{ids}")

            # ---- 6. 搜索不能绕过 user_id 过滤 ----
            r = await cb.get("/notes", params={"keyword": A_TITLE, "size": 100})
            body = r.json()
            check(
                "B 搜不到 A 的笔记",
                body["total"] == 0,
                f"期望 total=0，实际 total={body['total']}，"
                f"命中的标题：{[i['title'] for i in body['items']]}",
            )

            # ---- 7. 标签列表 ----
            r = await cb.get("/tags")
            tags = {t["name"]: t["note_count"] for t in r.json()}
            check("B 看不到 A 的标签", A_TAG not in tags, f"实际标签：{tags}")
            expect("B 自己标签的 note_count 正确", tags.get(B_TAG), 1)

            # ---- 8. A 删掉之后再打，仍是 404 而不是 403/500 ----
            # 前置必须是 A 真删成功了，否则 B 的 DELETE 照样返回 404，这条会假绿
            r = await ca.delete(f"/notes/{note_a}")
            expect("A 自己删笔记返回 204", r.status_code, 204)
            if r.status_code == 204:
                a_ids.remove(note_a)
            r = await cb.delete(f"/notes/{note_a}")
            expect("A 删掉后 B 再删仍是 404", r.status_code, 404)

        finally:
            # 分两份清理：用错 client 会删出 404，日志会说谎
            for i in a_ids:
                try:
                    r = await ca.delete(f"/notes/{i}")
                    if r.status_code != 204:
                        print(f"[清理A] 笔记 {i} 未删掉：{r.status_code} {r.text[:60]}")
                except Exception as e:
                    print(f"[清理A] 笔记 {i} 请求失败：{type(e).__name__}: {e}")
            for i in b_ids:
                try:
                    r = await cb.delete(f"/notes/{i}")
                    if r.status_code != 204:
                        print(f"[清理B] 笔记 {i} 未删掉：{r.status_code} {r.text[:60]}")
                except Exception as e:
                    print(f"[清理B] 笔记 {i} 请求失败：{type(e).__name__}: {e}")

    ok_count = sum(1 for r in results if r[1])
    print(f"\n通过 {ok_count}/{len(results)}")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name}: {detail}")
    if ok_count != len(results):
        raise SystemExit(1)


asyncio.run(main())
