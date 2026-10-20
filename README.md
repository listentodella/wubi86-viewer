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

- `public/fonts/lxgw-wenkai-roots.woff2`：LXGW WenKai（霞鹜文楷）子集，仅含 138 个命名字根，SIL OFL 1.1；许可见 `public/fonts/LXGW-WenKai-OFL.txt`。
- 字根表页可在「楷体 / 黑体」之间切换；无名字形仍使用书中黑体字根路径。

## 数据

| 文件 | 来源 |
| --- | --- |
| `data-src/ms-wubi.tsv` | 本机 `C:\Windows\InputMethod\CHS\ChsWubiNew.lex`（`npm run extract` 导出） |
| `data-src/data-wubi-v86.tsv` 等 | [sdcb/search-wubi](https://github.com/sdcb/search-wubi) 字根拆解、识别码 |
| `data-src/hanzi-writer-data/` | [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) 笔画矢量（Arphic Public License） |
| `data-src/黑体字根.ttf` | 字根字形；**来源不详、无授权信息**（见 [docs/font-provenance.md](docs/font-provenance.md)） |
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
npm run dev
```

推送到 `main` 后由 GitHub Actions 生成数据、构建并发布到 Cloudflare Pages（需要 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_PAGES_PROJECT` 三个 secret）。

## 许可

本项目源代码以 [GNU AGPL-3.0](LICENSE) 许可开源。`data-src/` 中的第三方数据各自遵循其原始许可（见上表）。
