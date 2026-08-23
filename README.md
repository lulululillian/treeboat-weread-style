# 微信读书阅读统计 · 可分享模板

基于官方「微信读书」skill 网关接口（`i.weread.qq.com/api/agent/gateway`）的个人阅读统计仪表盘：
输出到 Obsidian（DataviewJS 渲染），内置 **7 套配色主题**（米棕暖调 / 黛蓝雾灰 / 抹茶奶油 / 香芋紫 / 砖红拿铁 / 珊瑚奶油 / 雾蓝银灰）、**封面横向画廊自动滚动**、**周环比进度条**、**热力图**、**前端换肤下拉**。

模板已去除所有本地绝对路径，朋友拿到后只需填写自己的 API key 与 Obsidian 库路径即可使用。

---

## 使用方式（拿到压缩包后）

**方式一：交给 AI 助手配置（推荐）**
1. 解压 `weread-readstats-template.zip`，得到 `README.md` 和 `weread_tmp/` 文件夹；
2. 把整个文件夹路径发给你的 AI 助手（如 Marvis），告诉它「帮我按 README 配置这个微信读书阅读统计模板」；
3. AI 会读取 `README.md` 和 `config.json`，引导你：新建 Obsidian 库（或告诉你填现有库路径）、获取 API key、填写 config.json、运行刷新，全程不需要手动改脚本。

**方式二：完全手动配置**
1. 解压压缩包；
2. 按下面「配置步骤」完成 API key 与 config.json 填写；
3. 在项目目录运行 `python weread_tmp/refresh.py` 一键刷新；
4. 用 Obsidian 打开库，打开 `微信读书/阅读统计/阅读统计.md` 查看仪表盘。

> 无论哪种方式，**都不需要安装额外的 Python 包**（仅用标准库），Python 3.8+ 即可；唯一需要的是 Obsidian 的 Dataview 社区插件。

---

## 目录结构

```
weread-readstats-template/
├── README.md
└── weread_tmp/
    ├── config.json              # ← 唯一需要修改的配置文件
    ├── config.py                # 公共配置加载器（自动读取 config.json）
    ├── refresh.py               # 一键刷新：拉数据 → 生成看板 → 同步书架笔记
    ├── prep_dash.py             # 由 monthly.json 实时计算 dash_data.json
    ├── gen_html.py              # 周/月/天三视图渲染组件（主题/画廊/换肤）
    ├── gen_dv.py                # 生成 Obsidian DataviewJS 版阅读统计.md
    ├── sync_notes.py            # 同步实时进度/划线回写「我的书架」笔记
    ├── archive_month.py         # 归档指定历史月份（生成 data/YYYY-MM.json）
    ├── gen_monthly_summary.py   # 生成月度总结（阅读月报）
    └── themes.json              # 7 套主题配色存档（含当前主题）
```

> 运行后会生成 `monthly.json`、`dash_data.json`、`data/` 归档等数据文件（自动创建，可随时删除重建）。

---

## 零、从零开始：没有 Obsidian 库怎么建

如果你还没有 Obsidian 库，按下面三步建一个（只使用通用大分类，示例路径可自定义，但不建议再细拆）：

### 1. 新建 Obsidian 库
1. 下载并安装 Obsidian（[obsidian.md](https://obsidian.md)，支持 Windows / macOS / Linux）。
2. 打开 Obsidian → 「创建新库」（Create new vault）→ 填写库名（任意，例如 `我的笔记` / `MyNotes`）→ 选择存放位置 → 创建。
3. 创建后 Obsidian 会自动在该目录生成 `.obsidian` 配置文件夹，这个目录就是 `vault_root`（config.json 里要填它）。

### 2. 建两个大分类目录
在库根下新建两个一级目录（分类逻辑：按「阅读平台 / 内容类型」分大块，不要再细分层级）：

```
我的笔记/                          ← 你的库根（vault_root）
├── 微信读书/                     ← 阅读数据大类
│   └── 阅读统计/                 ← 看板输出目录（stats_rel_dir）
└── 书影音/                       ← 书籍内容大类
    └── 我的书架/                 ← 书架笔记目录（shelf_rel_dir）
```

> 目录结构只有这两层大分类，后续所有书籍笔记、看板、归档都放这里，不额外建子分类，避免维护成本。

### 3. 建好后的 config.json 对应关系
| 配置项 | 对应填法（以上面示例） |
|---|---|
| `vault_root` | 你的库根绝对路径，如 `D:/我的笔记/Obsidian/我的笔记`（`.obsidian` 所在层） |
| `stats_rel_dir` | `微信读书/阅读统计` |
| `shelf_rel_dir` | `书影音/我的书架` |
| `scripts_dir` | `weread_tmp`（不动） |

`微信读书/阅读统计` 目录脚本会自动创建；`书影音/我的书架` 目录建议手动建好（书架笔记会写到这里，匹配规则见常见问题 Q6）。

---

## 一、配置步骤

### 1. 获取 API key
1. 在微信读书 skill 中按官方说明生成你的 `WEREAD_API_KEY`（个人令牌，不要泄露）。
2. 两种生效方式任选其一：
   - 写入环境变量：`export WEREAD_API_KEY="你的key"`（写入 `~/.bashrc` / `~/.profile` 可长期生效）；
   - 或直接在 `~/.bashrc` 末尾追加一行：`WEREAD_API_KEY="你的key"`。
3. 脚本读取顺序：环境变量 `WEREAD_API_KEY` → `~/.bashrc` → `~/.profile`。模板不保存你的 key。

### 2. 修改 weread_tmp/config.json
打开 `weread_tmp/config.json`，填写三处：

| 配置项 | 说明 | 示例 |
|---|---|---|
| `vault_root` | 你的 Obsidian 库**根目录**（`.obsidian` 所在目录，即库名那一层） | `D:/我的笔记/Obsidian/我的库名` |
| `stats_rel_dir` | 阅读统计输出目录（相对库根，可含子目录） | `微信读书/阅读统计` |
| `shelf_rel_dir` | 书架笔记目录（相对库根，需与你的书架笔记位置一致） | `书影音/我的书架` |
| `scripts_dir` | 脚本目录名（一般不用改） | `weread_tmp` |

- 目录可暂不存在，脚本会自动创建（除书架目录外）。
- 如果库根下还有一层专属子目录（例如 `资料归档`），把它拼进 `vault_root` 或相对目录均可，保持三段拼接结果与真实路径一致即可。
- 路径分隔符 `/` 与 `\` 均可。

### 3. 确认 Obsidian 插件
- 安装并启用 **Dataview** 插件（社区插件，用于渲染 `dataviewjs` 代码块）。
- `阅读统计.md` 需放在你的库内（`vault_root` 下），Obsidian 打开该笔记即可看到仪表盘。
- 书架笔记需存在（`shelf_rel_dir` 目录），`sync_notes.py` 会按书名匹配并写入/更新划线区块；未匹配到会自动新建笔记。

---

## 二、首次运行

在项目目录（`weread_tmp` 的父目录）执行：

```bash
python weread_tmp/refresh.py
```

`refresh.py` 会自动完成：
1. 调用微信读书接口拉取本月阅读数据 → 写 `monthly.json`；
2. 运行 `prep_dash.py` 计算 `dash_data.json`；
3. 归档当月数据到 `vault/data/YYYY-MM.json`，并更新本周快照；
4. 运行 `sync_notes.py` 同步书架笔记；
5. 运行 `gen_dv.py` 生成/更新 `阅读统计.md`（DataviewJS 版，含历史月份入口）。

> 失败兜底：任一步失败会自动回滚旧数据，看板不会被清空。

其他脚本（按需手动运行）：
```bash
# 生成指定历史月份的归档（如 2026-07）
python weread_tmp/archive_month.py 2026-07

# 生成月度总结（默认上月，可在每月 1 号定时执行）
python weread_tmp/gen_monthly_summary.py
python weread_tmp/gen_monthly_summary.py 2026-07
```

---

## 三、定时任务建议

| 频率 | 命令 | 说明 |
|---|---|---|
| 每日（建议早上） | `python weread_tmp/refresh.py` | 更新本月看板 + 书架笔记 + 周快照 |
| 每月 1 号 | `python weread_tmp/gen_monthly_summary.py` | 生成上月阅读月报 |

**Windows（任务计划程序）**：搜索「任务计划程序」→ 创建基本任务 → 触发器选「每天/每月」→ 操作选「启动程序」，程序填 `python`，参数填脚本绝对路径，起始于填项目目录。

**macOS / Linux（cron）**：
```cron
# 每天 07:00 刷新
0 7 * * * cd /path/to/你的项目目录 && /usr/bin/python3 weread_tmp/refresh.py >> weread_tmp/run.log 2>&1
# 每月 1 日 08:00 生成上月月报
0 8 1 * * cd /path/to/你的项目目录 && /usr/bin/python3 weread_tmp/gen_monthly_summary.py >> weread_tmp/run.log 2>&1
```

> 定时任务需确保能读取 API key：Windows 下把 `WEREAD_API_KEY` 设为系统环境变量；Linux/macOS 下脚本会自动读 `~/.bashrc` 兜底（`export WEREAD_API_KEY="..."` 需写入 `.bashrc` 而非 `.profile` 时也可读取两者）。

---

## 四、常见问题

**Q1：提示 `WEREAD_API_KEY 缺失`？**
脚本找不到 key。检查：环境变量是否已 export 且新开终端生效；`~/.bashrc` 中是否有 `WEREAD_API_KEY="..."`（注意引号）；Windows 定时任务请用系统环境变量。

**Q2：`config.json 缺少 vault_root`？**
`vault_root` 为空或文件缺失。填写 Obsidian 库根目录绝对路径后重试。

**Q3：Obsidian 里看不到仪表盘/显示空白？**
确认已启用 Dataview 插件且开启了 JavaScript 渲染；确认 `阅读统计.md` 在库内；打开开发者控制台看是否有 JS 报错。

**Q4：历史月份入口没有出现？**
需要每月数据归档。`refresh.py` 会自动归档当月；补历史月用 `archive_month.py 2026-07`。归档文件在 `vault/data/YYYY-MM.json`。

**Q5：「较上周日均」一直显示数据不足？**
周环比需要至少运行过上一周。连续每日刷新后会自动出现。

**Q6：书架笔记没匹配上/总是新建？**
匹配规则：先精确书名 `.md` → 短名 `.md` → 归一化（去括号/冒号）匹配。请确认书架目录与 `shelf_rel_dir` 一致、笔记文件名与书名一致。

**Q7：换肤下拉能记住我的选择吗？**
能。主题选择保存在浏览器 localStorage（`weread-wr-theme`），下次打开自动应用。

**Q8：会写 frontmatter 吗？**
仪表盘 `阅读统计.md` 无 frontmatter，直接输出 `dataviewjs` 代码块；书架笔记只更新「📝 微信读书划线」区块与 status，不破坏原有 frontmatter。

---

## 隐私说明
- 模板不含任何用户的 API key、用户名或本地绝对路径。
- API key 仅存于你自己的环境变量 / `~/.bashrc`，不会写入任何脚本或数据文件。
- 分享前请确认 `config.json` 已替换为你朋友的库路径，且不要包含 `monthly.json`、`dash_data.json`、`bm_*.json`、`notebooks.json`、`ids.txt`、`err*.log`、`week-snapshots`、归档 `data/*.json` 等个人数据文件。
