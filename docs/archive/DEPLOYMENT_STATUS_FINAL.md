# 部署状态最终报告

> 检查时刻：2026-10-02 23:26（北京）/ 15:26 UTC
> 阶段：仅部署 + 最小验证（未修改任何代码）

---

## 【部署】

| 项 | 结果 |
| --- | --- |
| **push 是否成功** | ❌ **NO — 推送失败** |
| **remote HEAD** | **`d8befd441f3ba44e6654dea1c81be1ee0e19f2b9`** |
| **local HEAD** | **`138f9e0eca7d23b0b4692e53b0025df92561d19f`** |
| **workspace 状态** | ✅ **clean**（仅 untracked `__pycache__/` 缓存目录） |

---

## 详细信息

### 1. 只读检查结果

| 检查项 | 值 |
| --- | --- |
| `git status --short` | `?? dashboard/__pycache__/`、`?? tests/__pycache__/`（无业务文件修改） |
| `git log -1 --oneline` | `138f9e0 fix(review): preserve entry price and market context fields` |
| `git rev-parse origin/main` | `d8befd441f3ba44e6654dea1c81be1ee0e19f2b9` |
| `git log origin/main..HEAD --oneline` | 1 条（`138f9e0`） |

### 2. 前置条件确认 ✅

| 项 | 期望 | 实际 | 状态 |
| --- | --- | --- | --- |
| HEAD | `138f9e0eca7d23b0b4692e53b0025df92561d19f` | 同左 | ✅ |
| origin/main | `d8befd441f3ba44e6654dea1c81be1ee0e19f2b9` | 同左 | ✅ |
| origin/main..HEAD commit 数 | 1 | 1 | ✅ |
| 工作区 | clean | clean | ✅ |

### 3. Push 执行结果 ❌

```
fatal: unable to access 'https://github.com/wijouyang-lab/us.git/':
Failed to connect to github.com port 443 after 134727 ms:
Couldn't connect to server
```

**连续 6 次尝试全部失败**（含本次）：
| # | 错误类型 |
|---|---|
| 1 | `Invalid username or token. Password authentication is not supported` |
| 2 | `Failed to connect to github.com port 443 after 135989 ms` |
| 3 | `Invalid username or token. Password authentication is not supported` |
| 4 | `GnuTLS recv error (-110): The TLS connection was non-properly terminated` |
| 5 | `Failed to connect to github.com port 443 after 133603 ms` |
| 6 | `Failed to connect to github.com port 443 after 134727 ms` |

---

## 【字段修复】

| 项 | 结果 |
| --- | --- |
| **commit** | `138f9e0eca7d23b0b4692e53b0025df92561d19f`（message: `fix(review): preserve entry price and market context fields`） |
| **4 个文件是否保持不变** | ✅ **是** — 仅 `review.py`、`dashboard_export.py`、`app.js`、`tests/test_review_dashboard_fields.py` |
| **测试是否仍为 241/241** | ✅ **是** — 全部通过 |

### 修复后的三价格语义（MSFT 2026-08-21）

| 字段 | 值 | 语义 |
| --- | --- | --- |
| 买入价 `rec_price` | **479.88** | 正式买入价 = 推荐日真实 Open |
| Price `price` | **515.96** | 当前市场价格（未改变） |
| Prev Close `prev_close` | **483.24** | 前收（未改变） |

---

## 【今日 Scan】

| 项 | 结果 |
| --- | --- |
| **是否发现 Run #149** | ❌ **无法确认** |
| **最新 Scan event** | `schedule`（Run #148） |
| **最新 Scan status** | `completed / success`（Run #148） |
| **是否发现 2026-10-02 13:07 UTC scheduled event** | ❌ **无法确认** |

无法确认的原因：GitHub 凭据失效（API `401 Bad credentials`），且当前环境无可自动恢复的授权机制（credential helper 返回空、`gh` 未登录、无环境变量 token），因此无法访问远端 run records 进行只读确认。

---

## 结论（只给事实）

1. 工作区无未提交的业务文件修改 ✅
2. HEAD = `138f9e0eca7d23b0b4692e53b0025df92561d19f` ✅
3. 本次修复 commit 未重复提交 ✅
4. 修改文件仍为 4 个：review.py / dashboard_export.py / app.js / tests/test_review_dashboard_fields.py ✅
5. **Push 失败**：凭据失效（401）+ 网络超时（github.com:443 不可达）❌
6. **今日 Run #149 是否存在**：无法确认（同上）❌

**当前本地已就绪的 commit `138f9e0` 等待推送，推送受限于环境 GitHub 授权失效，需重新授权后再执行 push。**