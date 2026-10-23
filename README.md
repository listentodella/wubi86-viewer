# 五笔字根图解（wubi86-viewer）

86 版五笔学习站：输入汉字、词语或五笔编码，田字格按字根分色高亮，并自动讲解取码规则（键名字、成字字根、末笔字型识别码、简码、词组规则）。

线上地址：<https://wubi.sdcb.ai>

[![查询「胜」：田字格字根分色高亮与取码讲解](docs/screenshot-char.png)](https://wubi.sdcb.ai/?q=胜)

[![查询「今天吃什么」：推荐打法与优化打法](docs/screenshot-sentence.png)](https://wubi.sdcb.ai/?q=今天吃什么)

## 功能

- 汉字 / 词语 → 微软五笔的全部编码（含简码），候选顺序与系统一致
- 句子 / 未收录词组 → 推荐打法：按微软词库动态规划切分，给出免选重的推荐打法，以及允许数字选重、更省键的优化打法
- 编码 → 汉字 / 词语（支持前缀「继续输入」，第 3、4 位可用 Z 万能键）
- 田字格字根高亮：悬停编码字母即高亮对应笔画，支持拆解演示与笔顺演示
- 字根键盘表、取码规则速记
- **字根反查**（查询页「字根反查：由字根找例字」）：点键位 → 选字根 → 列出含有它的汉字，
  例字按「能用 Make Me a Hanzi 重绘」优先、再按常用度排序，带绿角标的字可直接照它抽笔画重绘字根
- 查询记录保存在 localStorage：易忘标记、删除、清空、导入导出、复习卡片
- 练习：随机默写五笔全码；分级练习按书中路线（指法热身、键名、成字字根、单笔画、一简、二简、识别码、常用字 500/1500/3000）逐层推进；跟打练习支持古文与常用字范本（任意输入法）

## 移动端 / PWA

- 手机浏览器打开站点后「添加到主屏幕」即可独立窗口运行：iOS Safari「分享 → 添加到主屏幕」，Android Chrome「安装应用」。
- 窄屏（<640px）使用底部标签栏（查询 / 字根 / 复习 / 练习），顶部只保留记录、主题与 GitHub；输入框自动避让软键盘。
- Service Worker 预缓存应用外壳与 `roots.json` / `tiers.json`；查过的字词分片按需缓存 30 天（最多 800 个），离线可继续查看已访问内容与字根表。
- 新版本发布后重新打开一次即后台更新（`registerType: 'autoUpdate'`）。
- 本地验证 PWA 需要构建产物：`npm run build && npm run preview`；`npm run dev` 不注册 Service Worker。

## 学习资料

- [五笔学习路线与必练字表](docs/wubi-learning.md)：据晓览《五笔字型入门指南》整理，含键名、一级简码、二级简码、识别码与常用字分层字表。

## 字根表里的书中原图

字根表页选中键位后，右侧会显示该键在书中的键框图（楷体，含提笔等书写变体），数据字形在左，便于对照。图片位于 `public/chart-keys/`，由 PDF 第 20 页矢量图裁切旋转而来。

## 字体

- `data-src/文楷字根.ttf`：**黑体字根.ttf 的楷体版本**——码位（677 个 PUA + 9F 段）、字形数、字宽与 `黑体字根.ttf` 完全一致，
  字形取自 LXGW WenKai（霞鹜文楷，SIL OFL 1.1），15 个识别码字形由文楷笔画合成。可直接替换 `黑体字根.ttf` 使用。
  生成脚本 `scripts/build-kai-roots-font.py`，映射表 `scripts/kai-roots-map.json`，逐字来源与置信度见
  [docs/kai-roots-map.md](docs/kai-roots-map.md)；许可见 `data-src/文楷字根-OFL.txt`。
- `public/fonts/lxgw-wenkai-roots.woff2`：LXGW WenKai（霞鹜文楷）子集，仅含 138 个命名字根，SIL OFL 1.1；许可见 `public/fonts/LXGW-WenKai-OFL.txt`。
- 字根表页可在「楷体 / 黑体」之间切换；无名字形仍使用书中黑体字根路径。

### 核对与修正文楷字根

402 个 PUA 里有一部分是自动按轮廓匹配的，可能对不上。核对方式：

```bash
npm run review:kai                       # 生成 reports/kai-roots/文楷字根-核对.{html,tsv}
```

- 打开 `文楷字根-核对.html`：逐行显示 黑体 → 楷体、当前猜测、6 个备选（都是文楷字形），
  **每行自带「对 / 错」按钮 + 答案 + 备注输入框**；核对完点右下角「复制结果」，把文本贴回对话即可
  （判定存在浏览器 localStorage，刷新/重新生成都不会丢）。
- **行号 = 按 PUA 码位升序，固定不变**（修完重建也不会改号，和 `docs/kai-roots-map.md` 一致）；
  要按可疑度看，用「排序 → 形似度低→高」；已核对的行标「人工」，默认被「只看未判定」筛掉。
  顶部三个筛选勾选框（站内 ●／低中置信／形似度 < 0.25）可以只看需要处理的行；
  页面顶部的「部件字表 P1–P194」只是反馈时用的词汇表，不用逐条核对——开头 P1–P36 是 CJK 笔画（㇐横 ㇑竖 ㇒撇 ㇔点 ㇀提 ㇙竖提 …），
  正是「提、撇横、竖折」这类笔画型字根的准确写法。笔画型行（「轮廓」列为 1）的形似度天然偏低，看形状别看数字。
- TSV 版同样可用（`文楷字根-核对.tsv` 的「你的答案」列），写法：
  `3`（用候选 3）、`龶`（直接指定汉字）、`无`（确认没有楷体对应字，留空）、
  `黑体`（没有楷体对应字，保留黑体轮廓）、`P3`（用部件字表第 3 个）、
  `组丶`（这个字根是若干独立笔画，按黑体里每个笔画的框用「丶」逐个合成——如鬯/鹵/滷 的四点）。
- 写回并重建：

```bash
.venv/bin/python scripts/apply-kai-roots-review.py reports/kai-roots/文楷字根-核对.tsv
WENKAI_TTF=/path/LXGWWenKai-Regular.ttf npm run font:kai
```

`scripts/kai-roots-map.json` 里每个码位可以写成 `"龶"`、`""`（确认留空）或
`{"ch": "", "keep_hei": true, "note": "…"}`；手改同样会被保留。

### 正楷自动初审（Y 键试验）

```bash
npm run review:zheng:y    # 生成 reports/zhengkai-review/y.{html,json}
```

打开 `reports/zhengkai-review/y.html`：逐行对照黑体、当前正楷与 A/B/C 候选。
候选直接读取主页高亮用的 `r/seg`，附源字高亮、笔序与槽位适配预览；不需要来回反查。
判断支持浏览器本地保存、键盘选择、JSON 导入导出；**自动建议不等于人工确认，也不会自动改字体**。

确认后下载「判断 JSON」，先预览，再显式写入并重建：

```bash
npm run review:zheng:apply -- /path/zhengkai-review-y.json           # 只预览
npm run review:zheng:apply -- /path/zhengkai-review-y.json --write   # 写入确认表
npm run font:zhengkai
npm run review:zheng:y                                            # 检查最终字形
npm run roots:key                                                # 刷新原字根表（可选）
```

正楷确认单独存在 `scripts/zhengkai-roots-review.json`，不改文楷映射或既有人工取法；
报告过期或源数据变化时拒绝应用。完整说明见 [正楷自动初审](docs/zhengkai-review.md)。

## 数据

| 文件 | 来源 |
| --- | --- |
| `data-src/ms-wubi.tsv` | 本机 `C:\Windows\InputMethod\CHS\ChsWubiNew.lex`（`npm run extract` 导出） |
| `data-src/data-wubi-v86.tsv` 等 | [sdcb/search-wubi](https://github.com/sdcb/search-wubi) 字根拆解、识别码 |
| `data-src/hanzi-writer-data/` | [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) 笔画矢量（Arphic Public License） |
| `data-src/黑体字根.ttf` | 字根字形；**来源不详、无授权信息**（见 [docs/font-provenance.md](docs/font-provenance.md)） |
| `data-src/文楷字根.ttf` | 由 `黑体字根.ttf` + LXGW WenKai 生成的楷体版本（SIL OFL 1.1），`npm run font:kai` 可重建 |
| `scripts/root-names.json` | 非成字字根的中文名称（如“青字头”） |

候选顺序：词库每条记录带有权重，同一编码下按权重升序（与输入法候选顺序一致）。

### 字根笔画自动对齐

search-wubi 只为约 2,500 字提供了“笔画 → 字根”的对应关系。`scripts/lib/roots.mjs` 从这些样本中学习每个字根的笔画序列，
再对其余字做回溯搜索（允许包围结构拆成两段、允许 >4 根字中间不取码的笔画），失败时退化为编辑距离近似匹配。
近似结果会在页面上提示“自动推断”。

## 开发

```bash
npm install
npm run extract   # 仅在 Windows 上、词库更新时需要
npm run data      # 生成 public/data 分片 JSON
# 重建 data-src/文楷字根.ttf（文楷 TTF 自行下载，见 scripts/requirements-font.txt）
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements-font.txt
WENKAI_TTF=/path/LXGWWenKai-Regular.ttf npm run font:kai
npm run dev
```

推送到 `main` 后由 GitHub Actions 生成数据、构建并发布到 Cloudflare Pages（需要 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_PAGES_PROJECT` 三个 secret）。

## 许可

本项目源代码以 [GNU AGPL-3.0](LICENSE) 许可开源。`data-src/` 中的第三方数据各自遵循其原始许可（见上表）。
