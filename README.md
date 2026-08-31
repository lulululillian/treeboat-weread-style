# 舟读・微信读书 Obsidian 阅读看板

基于官方「微信读书」skill 网关接口（`i.weread.qq.com/api/agent/gateway`）的个人阅读统计仪表盘：
输出到 Obsidian（DataviewJS 渲染），内置 **7 套配色主题**（米棕暖调 / 黛蓝雾灰 / 抹茶奶油 / 香芋紫 / 砖红拿铁 / 珊瑚奶油 / 雾蓝银灰）、**封面横向画廊自动滚动**（点击封面直接跳转对应书架笔记）、**24小时环形时钟动效**（月/周/天三视图顶部概览嵌入，顺时针渐入填充，颜色深浅＝划线条数）、**周环比进度条**、**热力图**、**前端换肤下拉**、**月/周/天三视图**（读书卡按视图时间范围过滤：月视图全量、周视图仅本周、日视图仅当天）、**读完日期自动回写**（书架笔记 finish_date 字段，读完当天自动填充）。

模板已去除所有本地绝对路径，只需填写自己的 API key 与 Obsidian 库路径即可使用。

---

## 🚀 三步快速上手（小白也能看懂）

不需要懂代码，不需要会命令行，跟着下面三步走就行。

### 第一步：下载这个项目

选下面任意一种方式下载：

**方式 A：让 AI 帮你下载（最简单，推荐）**

直接跟你的 AI 助手说这句话：

> 「帮我下载 GitHub 上的舟读微信读书阅读看板项目，地址是 https://github.com/lulululillian/treeboat-weread-style，下载后解压好」

AI 会自动帮你下载并解压，你直接跳到第三步。

**方式 B：自己手动下载（5 步搞定）**

1. 用浏览器打开项目主页：https://github.com/lulululillian/treeboat-weread-style
2. 点击页面中间偏右的绿色按钮「**<> Code**」
3. 在弹出的小窗口最下方，点击「**Download ZIP**」
4. 等待下载完成，你会得到一个叫 `treeboat-weread-style-main.zip` 的压缩包
5. 解压它：
   - **Windows**：右键压缩包 → 「全部解压」→ 点「解压」
   - **Mac**：双击压缩包，自动解压

解压后你会得到一个文件夹，里面有 `README.md` 和 `weread_tmp` 文件夹。

### 第二步：认识这个文件夹（里面有什么）

打开解压后的文件夹，你会看到：

```
你的文件夹/
├── README.md          ← 就是你现在看的这份说明书
└── weread_tmp/        ← 核心文件夹，所有程序都在里面
    ├── config.json    ← ⭐ 唯一需要你改的文件（填你的 Obsidian 库路径等）
    ├── refresh.py     ← 🔄 一键刷新（运行它就会更新你的阅读看板）
    ├── update.py      ← ⬆️ 一键更新（有新版本时运行它）
    └── 其他十几个文件  ← 不用管，程序自动运行
```

> **你只需要记住两个文件**：`config.json`（配置）和 `refresh.py`（刷新）。其他文件不用碰，也不用懂。

### 第三步：让 AI 帮你配置（推荐）

1. 找到你解压后的**整个文件夹**的路径（就是包含 `weread_tmp` 和 `README.md` 的那一层）
   - 不知道路径在哪？打开文件夹，点击顶部地址栏，复制那一长串地址就是路径
2. 把这个路径发给你的 AI 助手（或者直接把文件夹拖到 AI 对话框里）
3. 跟 AI 说：

> 「帮我按 README 配置这个舟读微信读书 Obsidian 阅读看板」

AI 会一步步引导你完成所有配置：
- 如果你还没有 Obsidian 库，AI 会教你建一个
- 教你怎么获取微信读书 API key
- 帮你填好配置文件
- 运行第一次刷新，生成你的阅读看板

全程跟着 AI 说的做就行，不需要你自己改代码。

> **后续更新**也很简单：把项目文件夹路径发给 AI，说「帮我更新到最新版本」，AI 会自动搞定，你的配置和主题选择不会丢失。

---

## 查看方式选择

配置时 AI 会问你想用哪种方式查看，你也可以提前了解：

| 查看方式 | 适合谁 | 怎么看 |
|---|---|---|
| **Obsidian 仪表盘**（推荐） | 愿意装 Obsidian，想要完整功能 | 在 Obsidian 里打开 `微信读书/阅读统计/阅读统计.md`（总览页） |
| **纯网页** | 不想装 Obsidian，双击就能看 | 浏览器打开 `微信读书/阅读统计/阅读统计.html` |
| **两者都要** | 自己用 Obsidian，也想分享网页给朋友 | 两种都生成 |

- **Obsidian 版**功能最全：周/月/天三视图切换、总览页按月份筛选、前端换肤、封面点击跳转笔记、书架笔记可跳回；
- **文件结构**：`阅读统计.md` 是**总览页**（各月概览卡片 + 月份下拉筛选，点击进入任意月份）；当前月文件按月份命名（如 `9月阅读统计.md`），历史月带年份（如 `2026年8月阅读统计.md`）；
- **双向跳转**：阅读统计 → 书架笔记（点封面/读书卡），书架笔记 → 阅读统计总览（划线区块顶部「🔙 返回阅读统计总览」链接），Obsidian 自动建立反向链接；
- **网页版**不需要装任何软件，浏览器直接打开，功能和观感与 Obsidian 版一致；
- 这个选择写在 `config.json` 的 `output_mode` 里，以后想改随时可以改。

> 无论选哪种方式，**都不需要安装额外的 Python 包**（仅用标准库），电脑上有 Python 3.8+ 就行；只有选 Obsidian 版需要在 Obsidian 里装一个叫 Dataview 的免费插件（AI 会教你装）。

---

## 目录结构

```
weread-readstats-template/
├── README.md
└── weread_tmp/
    ├── config.json              # ← 唯一需要修改的配置文件
    ├── config.py                # 公共配置加载器（自动读取 config.json）
    ├── refresh.py               # 一键刷新：拉数据 → 生成看板 → 同步书架笔记
    ├── update.py                # 一键自动更新：从 GitHub 拉取最新脚本（保留你的配置）
    ├── prep_dash.py             # 由 monthly.json 实时计算 dash_data.json
    ├── gen_html.py              # 周/月/天三视图渲染组件（主题/画廊/换肤/环形时钟）
    ├── gen_dv.py                # 生成 Obsidian DataviewJS 版阅读统计.md
    ├── sync_notes.py            # 同步实时进度/划线回写「我的书架」笔记
    ├── archive_month.py         # 归档指定历史月份（生成 data/YYYY-MM.json）
    ├── gen_monthly_summary.py   # 生成月度总结（阅读月报）
    └── themes.json              # 7 套主题配色存档（含当前主题）
```

> 运行后会生成 `monthly.json`、`dash_data.json`、`data/` 归档等数据文件（自动创建，可随时删除重建）。

---

## 一、从零开始：没有 Obsidian 库怎么建

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

## 二、配置步骤

### 1. 获取 API key
1. 打开手机**微信读书** App → 右下角「我的」→ 右上角「设置」→ 找到「微信读书 Skill」→ 进入后下拉找到「获取 API Key」，点击生成并复制。
   （备用：电脑浏览器打开 https://weread.qq.com/r/weread-skills ，点击「快速配置」并用手机微信扫码，登录成功后页面会显示同样的 Key。）
2. 获取到以 `wrk-` 开头的 **API Key** 后，两种生效方式任选其一：
   - 写入环境变量：`export WEREAD_API_KEY="你的key"`（写入 `~/.bashrc` / `~/.profile` 可长期生效）；
   - 或直接在 `~/.bashrc` 末尾追加一行：`WEREAD_API_KEY="你的key"`。
3. 脚本读取顺序：环境变量 `WEREAD_API_KEY` → `~/.bashrc` → `~/.profile`。模板不保存你的 key。

> Key 绑定你的微信读书账号，数据仅你可见；除非主动重置，否则长期有效。请妥善保管，**不要公开发布或发给他人**。

### 2. 修改 weread_tmp/config.json
打开 `weread_tmp/config.json`，填写三处：

| 配置项 | 说明 | 示例 |
|---|---|---|
| `vault_root` | 你的 Obsidian 库**根目录**（`.obsidian` 所在目录，即库名那一层） | `D:/我的笔记/Obsidian/我的库名` |
| `stats_rel_dir` | 阅读统计输出目录（相对库根，可含子目录） | `微信读书/阅读统计` |
| `shelf_rel_dir` | 书架笔记目录（相对库根，需与你的书架笔记位置一致） | `书影音/我的书架` |
| `scripts_dir` | 脚本目录名（一般不用改） | `weread_tmp` |
| `output_mode` | 输出模式：`md`（Obsidian 版）/ `html`（纯网页版）/ `both`（两者都生成） | `md` |

- 目录可暂不存在，脚本会自动创建（除书架目录外）。
- 如果库根下还有一层专属子目录（例如 `资料归档`），把它拼进 `vault_root` 或相对目录均可，保持三段拼接结果与真实路径一致即可。
- 路径分隔符 `/` 与 `\` 均可。

### 3. 确认 Obsidian 插件（仅 `md` / `both` 模式需要）
- 安装并启用 **Dataview** 插件（社区插件，用于渲染 `dataviewjs` 代码块）：
  1. Obsidian 左下角点击「设置」（齿轮图标）→ 左侧「第三方插件」；
  2. 若显示「安全模式（Restricted mode）已开启」，点击关闭（Obsidian 需要先允许社区插件）；
  3. 点击「浏览」（Browse）→ 搜索框输入 `Dataview` → 找到 **Dataview**（作者 blacksmithgu）→ 点击「安装」（Install）；
  4. 安装后点击「启用」（Enable）；启用后在「已安装插件」列表里能看到 Dataview 且开关为打开状态。
- 总览页 `阅读统计.md` 需放在你的库内（`vault_root` 下），Obsidian 打开即可看到各月总览与月份筛选；点击月份卡片进入对应月统计（如 `9月阅读统计.md`）。
- 书架笔记需存在（`shelf_rel_dir` 目录），`sync_notes.py` 会按书名匹配并写入/更新划线区块；未匹配到会自动新建笔记。
- 选 `html` 模式的朋友**跳过本节**，不需要安装任何 Obsidian 插件。

---

## 三、网页模式（不想用 Obsidian 也可以）

如果不想装 Obsidian，`output_mode` 设为 `html` 即可，看板输出为独立网页，浏览器双击打开：

1. `weread_tmp/config.json` 中把 `"output_mode"` 改为 `"html"`；
2. 在项目目录运行 `python weread_tmp/refresh.py`；
3. 打开 `微信读书/阅读统计/阅读统计.html`（无需 Obsidian、无需任何插件）。

说明：
- 网页版包含周 / 月 / 天三视图切换、7 套配色换肤（选择会记住）、封面画廊自动滚动（点击封面跳转对应书架笔记）、24小时环形时钟动效、周环比进度条，与 Obsidian 版一致的观感；
- 三视图读书卡按时间范围过滤：月视图展示本月全部书籍，周视图仅展示本周有划线的书，日视图仅展示当天有划线的书；
- `html` 模式不生成 md 文件；`both` 模式则 Obsidian 版和网页版同时生成；
- 网页版是单文件自包含（数据内嵌），可以复制给手机 / 发给朋友直接打开看。

---

## 四、首次运行

在项目目录（`weread_tmp` 的父目录）执行：

```bash
python weread_tmp/refresh.py
```

`refresh.py` 会自动完成：
1. 调用微信读书接口拉取本月阅读数据 → 写 `monthly.json`；
2. 运行 `prep_dash.py` 计算 `dash_data.json`；
3. 归档当月数据到 `vault/data/YYYY-MM.json`，并更新本周快照；
4. 运行 `sync_notes.py` 同步书架笔记；
5. 按 `output_mode` 生成总览页 `阅读统计.md`（Obsidian 版，含各月概览与月份筛选）+ 当月 `X月阅读统计.md`，和/或 `阅读统计.html`（网页版）；
6. 生成后自动检查并清除外部同步服务注入的 AIGC frontmatter（有则删除，控制台打印 `aigc cleaned: ...`）。

> 失败兜底：任一步失败会自动回滚旧数据，看板不会被清空。

其他脚本（按需手动运行）：
```bash
# 生成指定历史月份的归档（如 2026-07）
python weread_tmp/archive_month.py 2026-07

# 命令行生成月度总结（默认上月，可在每月 1 号定时执行；与下方按钮产物一致）
python weread_tmp/gen_monthly_summary.py
python weread_tmp/gen_monthly_summary.py 2026-07
```

**生成阅读月报（推荐，Obsidian 内一键）**：打开任意月份的阅读统计页（如 `8月阅读统计.md` 或 `2026年07月阅读统计.md`），点击右上角 **📊 月报** 按钮，会自动在同目录生成 `阅读月报-YYYY-MM.md` 并打开。月报数据图非常丰富（每日时长柱状图、月度热力图、每周习惯、24 小时时段环形、各书时长占比、阅读排行、划线排行、阅读状态、最佳划线、读书卡等），比单月统计视图的图更多。

---

## 五、如何更新到新版本

模板会持续更新（新功能 / 修复 / 优化），更新非常简单，**你的配置和主题选择会自动保留**。

### 方式一：让 AI 助手帮你更新（推荐，无需命令行）

大多数用户是通过 AI 智能体（如豆包等）来使用本模板的，更新也可以全程交给 AI，你只需要两步：

**第一步：找到你的项目文件夹**
就是你当初解压压缩包得到的那个文件夹，里面有 `weread_tmp` 文件夹和 `README.md` 文件。
- 如果忘了放在哪：打开文件资源管理器（此电脑），在右上角搜索框输入 `weread_tmp`，找到后往上一层就是项目文件夹。

**第二步：让 AI 帮你更新**
把项目文件夹的路径发给 AI（或者直接把文件夹拖到 AI 对话框），然后说：
> 「帮我把这个微信读书阅读看板更新到最新版本」

AI 会自动帮你完成：备份旧版本 → 从 GitHub 拉取最新脚本 → 保留你的配置和主题 → 刷新数据。

> 你的配置文件（库路径、API key 等）和主题选择不会被覆盖，更新后直接使用即可。

### 方式二：命令行一键更新（备选）

如果你熟悉命令行，也可以自己运行：

```bash
python weread_tmp/update.py
```

脚本会自动完成：
1. 备份当前版本到 `weread_tmp/_backup_时间戳/`（更新失败可回滚）；
2. 从 GitHub 拉取最新版本的所有脚本文件；
3. **自动保留你的 `config.json`（库路径配置）和 `themes.json`（主题选择），不会被覆盖**；
4. 显示更新结果（成功 / 失败的文件列表）。

更新完成后，运行一次刷新即可应用新版本：

```bash
python weread_tmp/refresh.py
```

> 如果某些文件下载失败（可能是网络连接 GitHub 不稳定），重新运行 `python weread_tmp/update.py` 即可，已成功更新的文件不受影响。

### 方式三：手动更新（备选）

如果自动更新一直失败，也可以手动更新：
1. 从 GitHub 下载最新的 `weread_tmp/` 里的 `.py` 文件；
2. 覆盖到你本地的 `weread_tmp/` 目录（**不要覆盖 `config.json` 和 `themes.json`**）；
3. 运行 `python weread_tmp/refresh.py`。

---

## 六、定时任务建议

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

## 七、常见问题

**Q1：提示 `WEREAD_API_KEY 缺失`？**
脚本找不到 key。检查：环境变量是否已 export 且新开终端生效；`~/.bashrc` 中是否有 `WEREAD_API_KEY="..."`（注意引号）；Windows 定时任务请用系统环境变量。

**Q2：`config.json 缺少 vault_root`？**
`vault_root` 为空或文件缺失。填写 Obsidian 库根目录绝对路径后重试。

**Q3：Obsidian 里看不到仪表盘/显示空白？**
确认已启用 Dataview 插件且开启了 JavaScript 渲染；确认 `阅读统计.md` 在库内；打开开发者控制台看是否有 JS 报错。

**Q4：历史月份入口没有出现？**
需要每月数据归档。`refresh.py` 会自动归档当月；补历史月用 `archive_month.py 2026-07`。归档文件在 `vault/data/YYYY-MM.json`。打开总览页 `阅读统计.md`，顶部会列出所有已归档月份的下拉与概览卡片，点击即可进入对应月统计（历史月文件名如 `2026年07月阅读统计.md`）。

**Q5：「较上周日均」一直显示数据不足？**
周环比需要至少运行过上一周。连续每日刷新后会自动出现。

**Q6：书架笔记没匹配上/总是新建？**
匹配规则：先精确书名 `.md` → 短名 `.md` → 归一化（去括号/冒号）匹配。请确认书架目录与 `shelf_rel_dir` 一致、笔记文件名与书名一致。

**Q7：换肤下拉能记住我的选择吗？**
能。主题选择保存在浏览器 localStorage（`weread-wr-theme`），下次打开自动应用。

**Q8：会写 frontmatter 吗？为什么有时顶部出现 AIGC 标记？**
仪表盘 `阅读统计.md` 无 frontmatter，直接输出 `dataviewjs` 代码块；书架笔记只更新「📝 微信读书划线」区块与 status，不破坏原有 frontmatter。
如果顶部出现 `--- AIGC: ... ---` 溯源标记（含 ContentProducer / ProduceID / ReservedCode），是外部同步/备份服务（如 fast-note-sync）在同步回本地时注入的，**不是脚本生成的**。脚本每次刷新后会自动检查并删除这类标记（控制台打印 `aigc cleaned: ...`）；根治办法是在该同步服务设置中关闭「AI 内容标记」或暂停同步验证。

**Q9：我写在书架笔记里的读书笔记/读后感会被覆盖吗？**
不会。`sync_notes.py` 只维护「## 📝 微信读书划线」区块（结束标记 `<!-- weread_marks_end -->` 之前），**该标记之后的内容以及划线区块之前的内容（标题、frontmatter、你自己的笔记/读后感）全部保留**，每次刷新仅替换划线数据与 status 字段。
- 已存在笔记：只在划线区块内更新，你写的内容无论放在区块前还是结束标记后都安全；
- 未匹配到书名的笔记：自动新建并写入划线区块，你可以在区块后任意追加自己的内容。
若你希望刷新后把划线区块移到别处，把 `<!-- weread_marks_end -->` 标记连同划线区块一起移动即可，脚本只认这个标记的位置。

**Q10：封面点击会跳转到哪里？三视图的读书卡为什么数量不一样？**
- 封面画廊的每本书封面都可以点击，直接跳转到 Obsidian 中对应的书架笔记（与读书卡右上角的「已链 [[书名]]」指向同一本笔记）。
- 三视图读书卡按时间范围过滤：月视图展示本月全部书籍（含进度、累计划线等完整信息）；周视图仅展示本周有划线的书，划线与最近阅读均限定在本周；日视图仅展示当天有划线的书。这样切换到周/日视图时，看到的就是对应时间段内真正读了的书，不会被全月列表淹没。

---

## 八、隐私说明
- 模板不含任何用户的 API key、用户名或本地绝对路径。
- API key 仅存于你自己的环境变量 / `~/.bashrc`，不会写入任何脚本或数据文件。
- 分享前请确认 `config.json` 已替换为你朋友的库路径，且不要包含 `monthly.json`、`dash_data.json`、`bm_*.json`、`notebooks.json`、`ids.txt`、`err*.log`、`week-snapshots`、归档 `data/*.json` 等个人数据文件。
