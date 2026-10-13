# PEP 701 技术债确认报告

> 范围：只读核查，不修改任何文件、不 push、不 rebase、不碰 workflow/代码。
> 仓库：`/tmp/us`，HEAD = `fedf63d`（ahead 6 / behind 2）。
> 核心问题：scan.py 是否因 PEP 701（Python 3.12 才允许 f-string 表达式内含反斜杠）在 < 3.12 环境编译失败？这是真实生产风险，还是纯技术债？
>
> 注：本报告写于 scan.py 长度约 2497 行时；此后文件已增长至约 2800 行，行号已漂移。当前触发点为 `scan.py:2813`（f-string 表达式内的反斜杠）。

---

## 1. 各 workflow 的 Python 版本

| workflow | setup-python | python-version | matrix | 是否 < 3.12 |
|---|---|---|---|---|
| `scan.yml` | `@v4` | `'3.12'`  `# ← 升级到这里` | 无 | 否 |
| `review.yml` | `@v4` | `'3.12'`  `# ← 同步升级，保持一致` | 无 | 否 |
| `evolve.yml` | `@v5` | `'3.12'` | 无 | 否 |
| `dashboard-data.yml` | `@v5` | `"3.12"` | 无 | 否 |

- **结论：4 个 workflow 全部固定 `3.12`，无 matrix，无任何版本 < 3.12。**
- `scan.yml:30` 与 `review.yml:32` 的注释（`升级到这里` / `同步升级，保持一致`）表明这是**近期有人为修复 PEP 701 而主动升级**的痕迹。

---

## 2. scan.py 触发点的具体写法

scan.py:2497 起是一个 `f"""` 三引号 f-string（风控 prompt 模板），到 scan.py:2503 闭合。

```python
2497→    prompt = f"""
2498→你是美股宏观风控总监。判断当前活跃持仓是否存在真正的突发利空/逻辑证伪。
2499→不要因为过去止损、过去低胜率就建议未来永久退出；只处理当前真实事件风险。
2500→
2501→宏观：\n{macro_news_text[:6000]}\n\n市场：\n{macro_market_text}\n\n持仓：\n{'\n'.join(position_lines)}\n
2502→仅输出：{{"decision":{{"TICKER":"Dropped|Active"}},"reason":"150字以内"}}
2503→"""
```

**PEP 701 特征所在（2501 行）：**

```python
持仓：\n{'\n'.join(position_lines)}\n
```

- `'\\n'` 是**位于 f-string 表达式部分 `{...}` 内部的反斜杠转义**。
- 按 PEP 701（Python 3.12 生效），f-string 表达式部分允许反斜杠；**3.12 之前这是 `SyntaxError`**。
- 另：2501 行 f-string 正文中也含 `\n` 字面量（body 反斜杠），同样受 PEP 701 约束，3.12 前非法。

### 实测编译验证（只读，未改文件）
- 本地默认 `python3` = **3.11.1**：
  ```
  File "scan.py", line 2503
      """
         ^
  SyntaxError: f-string expression part cannot include a backslash
  ```
  → 编译失败，错误即 PEP 701 特征（报错位置落在 f-string 闭合行 2503，根因是 2501 行的反斜杠）。
- 本地 `/usr/bin/python3.12` = **3.12.3**：
  ```
  >>> 3.12 编译通过（退出码 0）
  ```
- 即：生产 CI 用 3.12 能编译通过；本地 3.11 编译失败。与上一轮结论一致。

---

## 3. 仓库内的 Python 版本声明文件

| 文件 | 是否存在 |
|---|---|
| `.python-version` | **absent** |
| `pyproject.toml` | absent |
| `setup.cfg` | absent |
| `setup.py` | absent |
| `Pipfile` | absent |
| `runtime.txt` | absent |

- **无任何本地/依赖文件固化 Python 版本。** 版本要求仅散落在 4 个 workflow 的 `python-version:` 字段里。
- 这意味着：** contributors / 本地开发若用 3.11 跑 `python scan.py`，会直接 SyntaxError 起不来**，但 CI 永远用 3.12，故生产不受影响。

---

## 4. 结论

### 判定：**纯技术债，不是真实生产风险**

- **为什么不是真实风险**：所有跑 Python 的 workflow（scan/review/evolve/dashboard-data）都已 pin `3.12`；无 matrix、无回退版本；`scan.py` 在 3.12 下编译通过并被 CI 实际执行。生产链路不会因 PEP 701 失败。
- **真实暴露面（仅本地开发）**：缺少版本声明文件，本地 3.11 会踩坑，但这是"开发者环境便利性"问题，不是运行时缺陷。

### 受影响文件（仅本地开发体验，非生产）
- 触发点：`scan.py:2497–2503`（f-string 内含反斜杠，需 3.12+）。
- 周边同性质 f-string：`scan.py` 中多处含 body 反斜杠的 f-string（如 2039、2137–2142、2416、3218 等），在 3.12 前同样非法——但 3.12 下全部合法，无需改动。

### 建议（纯文档/卫生，可选，非紧急）
1. **加 `.python-version` = `3.12`**，让本地开发（pyenv / asdf）与 CI 一致，消除"本地 3.11 起不来"的困惑。
   - 代价：极低，一个单行文件。
   - 这是把"已隐式依赖 3.12"显式固化，不改变任何运行行为。
2. （可选）在 `README` 注明"需要 Python ≥ 3.12（PEP 701）"。
3. **不建议**为兼容 3.11 去改写 scan.py 的 f-string——那是退化，且会牺牲可读性；保持 3.12 基线即可。

> 注：本轮仅报告，未新增/修改任何文件（含未创建 `.python-version`）。是否落实建议由用户拍板。
