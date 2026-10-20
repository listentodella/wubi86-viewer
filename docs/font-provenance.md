# 字根字体来源与许可

## `data-src/黑体字根.ttf`

- 字体名：黑体字根（Regular），Version 1.00，2022-05-12。
- 结构：690 个字形、687 个码位，其中 671 个 PUA（E000 起），仅 10 个 Unicode（龰 龴 龵 龶 龷 龸 龹 龺 龻）。
- name 表只有 family/version，没有 copyright、license、designer、vendor URL；OS/2 vendID 为 `MS  `。
- 开源输入法项目 `huanfeng/WindInput` 的 `NOTICE.md` 明确写道：`HeiTiZiGen.ttf`「来源不详，无授权信息」；`qwertyyb/Fire` 也直接打包了同一文件。
- 结论：**不是有明确开源许可的字体**，来源与授权不明。仓库目前把它作为 `data-src` 数据源分发，存在许可风险；长期应替换。

## 楷体字根字体

- 在 GitHub 上检索 `楷体字根`、`KaiTiZiGen`、`五笔字根 楷体` 等，**没有找到开源的楷体字根 TTF**。
- 书中字根图（PDF 第 20 页）没有嵌入字体，全部是矢量轮廓，无法直接抽出楷体字根字体。
- 可行路线：
  1. 把 PUA 字根映射到 Unicode，用 LXGW WenKai（SIL OFL 1.1）渲染——本仓库正在做；
  2. 少量没有 Unicode 的真变体，保留现有路径或补绘 SVG；
  3. 若要用书中原图的楷体轮廓，需注意书图版权。

## 本站现状

- `roots.json` 的 `p` 是构建时从上述 TTF 提取的 SVG 路径；页面不加载 TTF，但路径是字体的衍生数据。
- `public/fonts/lxgw-wenkai-roots.woff2` 是 LXGW WenKai 的子集（SIL OFL 1.1），用于命名根的楷体显示；许可文件同目录。
