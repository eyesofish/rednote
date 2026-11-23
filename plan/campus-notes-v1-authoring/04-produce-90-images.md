# Subproblem 4: 制作 90 张独立配图

## 1. Goal

为 N011–N100 各做一张 4:3、可离线打开、能与正文关键物品对上的图片，并让 `notes.csv` 的 `image_path` 和 `image_source` 与实际文件一致。

## 2. Why this step exists

任务单要求“每篇配一张独立图片”，仓库校验器会检查 100 个图片文件与 `image_path` 一一对应、图片内容不能重复、格式与扩展名一致。图片也是用户验收时最先看的部分。

## 3. Files involved

- `.local/campus-authoring/build/campus-notes-v1/images/` - 最终 100 张图片的目录。N001–N010 从样稿复制，N011–N100 在本步骤新增。
- `.local/campus-authoring/build/campus-notes-v1/notes.csv` - 需要更新 N011–N100 的 `image_path` 和 `image_source`。
- `.local/campus-authoring/outline.csv` - 每行的 `image_brief` 和 `key_object` 是画面依据。
- `.local/campus-authoring/illustrations.py` - 方案 B 的实际生成器：用 Pillow 画 90 个 4:3 扁平场景，2 倍超采样后缩到 800×600，存成 JPEG。
- `.local/campus-authoring/campus-classmate-kit/campus-notes-v1/images/N001.webp` … `N010.webp` - 只读样稿，用来对照构图、光线和色调。

## 4. Exact changes

配图来源已由用户选定为方案 B（扁平插画）。下面保留三种方案作为记录，实际执行方案 B。先做 N011、N029、N065 三张试稿，确认后再批量制作剩余 87 张。

### 方案 A：用户供图

- 用户按 `outline.csv` 的 `image_brief` 提供 N011–N100，共 90 张。
- 文件名必须是 `N011.webp` … `N100.webp`（或统一 `.jpg`/`.png`）。
- 我们负责检查尺寸、体积、内容对应关系，并把 `notes.csv` 的 `image_path`、`image_source` 改成实际值。
- `image_source` 按用户实际来源填写：本人拍摄 / 本人绘制 / AI 生成。

### 方案 B：我们制作统一风格的扁平插画

- 工具改为本机 Python 3.13 + Pillow 13：Playwright 的 `file://` 被拦，`python -m http.server` 又被拒绝，Pillow 已确认可用，因此直接用 Pillow 在 1600×1200 画布上绘制，再缩到 800×600。
- 新建 `.local/campus-authoring/illustrations.py`，用几何图形画 90 个 4:3 场景；不使用 SVG/HTML，也不需要浏览器。
- 统一视觉规则：米色桌面或浅色背景，暖色调，单一主物居中偏下，环境只保留 1–2 个提示物，不出现可读文字和人脸；每个场景至少有一个与正文点名物品对应的主物。
- 每张先画 1600×1200，缩到 800×600，存 JPEG 质量 86，保存为 `images/N011.jpg` … `N100.jpg`。
- `notes.csv` 的 `image_path` 改成 `images/Nxxx.jpg`，`image_source` 填“本人绘制”。
- 先做 3 张试稿（N011、N029、N065），自己检查后再做剩余 87 张；不再阻塞等待用户确认。
- 注意：扁平插画与 N001–N010 的写实 AI 图风格不同，这是这个方案的已知取舍。

### 方案 C：用户提供图片生成 API

- 用户提供可调用的服务、密钥和模型名。
- 按 `image_brief` 生成 90 张写实风格图片，`image_source` 填“AI 生成”。
- 同样先出 3 张试稿，确认风格后再批量。
- 生成结果仍要逐张检查：4:3、≤500 KB、无重复、主物与正文一致。

无论哪种方案，都必须满足：

- 90 张内容互不相同；仓库校验器会用 SHA-256 拒绝重复图片。
- 每张宽高比为 4:3（例如 800×600、960×720、1200×900）。
- 单张不超过 500 KB；硬上限 4 MiB、1600 万像素。
- 图片格式与扩展名一致：WebP 配 `.webp`，JPEG 配 `.jpg`/`.jpeg`，PNG 配 `.png`。
- 缩略到手机大小，仍能认出正文点名的物品（笔、锅、伞、补丁、盒子等）。

## 5. Out of scope

- 不改标题和正文（除非图文明显对不上，回到 03 修改）。
- 不修改 `search-cases.csv`。
- 不打包 ZIP。
- 不用与正文无关的通用风景图凑数。

## 6. Done condition

- `images/` 下恰好 100 个图片文件，N001–N100 一一对应。
- 每张 4:3，单张 ≤500 KB，内容不重复。
- `notes.csv` 的 `image_path` 全部指向存在的文件，`image_source` 全部合法且真实。
- 90 张新图与各自正文的关键物品对应。

## 7. Verification

```sh
python .local/campus-authoring/illustrations.py
```

生成器自身会打印每张图的宽高、字节数和 SHA-256 前缀，并检查：90 张新图、800×600、最多 500 KB、哈希不重复。另用 Pillow 逐张重新打开确认 JPEG 有效。

- 文件数：`images/` 下 100 个文件。
- 尺寸与体积：逐张读取宽高和字节数，列出不是 4:3 或超过 500 KB 的文件。
- 唯一性：对 100 个文件做 SHA-256，确认没有重复。
- 对应性：随机抽 10 张，遮住正文只看图，猜它对应哪篇；猜不出就重做。
- 缩略图检查：把图片缩到约 320×240，确认主物仍可辨认。
- 最终由 06 的仓库校验器兜底。

## 8. Expected output

`.local/campus-authoring/build/campus-notes-v1/images/` 下 100 张图片，以及更新后的 `notes.csv`。

## 9. Notes for the next step

05 的搜索词审计只依赖文字；06 打包会同时检查图片。若用户选择方案 A，交付节奏会变成“先交文字和图片清单，用户补图后再打包”。

## 10. Risks or ambiguity

- **最大风险**：当前环境没有图片生成模型。方案 B 只能做扁平插画，无法复刻样稿的写实 AI 质感；方案 C 需要用户提供可调用服务；方案 A 需要用户投入拍摄/生成时间。
- 90 张图的制作量很大，先做 3 张试稿可以避免整批返工。
- 仓库校验器只检查技术参数（4:3、体积、唯一性），不检查“好不好看/贴不贴题”，所以人工抽查不能省。
- 使用 AI 生成图时，`image_source` 要如实填写；不要把手绘插画标成“AI 生成”或反过来。
