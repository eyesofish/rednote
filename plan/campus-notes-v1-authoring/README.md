# Task Plan: 校园图文笔记 100 篇（campus-notes-v1）

## Overall goal

把 `campus-classmate-kit.zip` 里的 10 篇样稿当作风格基准，补写 N011–N100 共 90 篇中文校园生活笔记，制作 90 张一对一配图，整理 5 组搜索词加 1 个零匹配词，最后把 `notes.csv`、`search-cases.csv` 和 `images/` 打成根目录平铺的 `campus-notes-v1.zip`。导入由用户自己处理，本计划不做导入。

成功标准：

- 共 100 篇，五个主题各 20 篇，编号 N001–N100 连续且唯一。
- 每篇标题 1–160 字，正文 80–200 字（目标 120–170 字），风格与 N001–N010 一致。
- 每篇一张独立图片，4:3，单张不超过 500 KB、1600 万像素；图片里的关键物品能在正文中找到。
- 5 组搜索词每组只命中“标题 1 篇 + 仅正文 1 篇”，另有 1 个零匹配词。
- 用仓库自带的 `app.campus_import validate` 校验通过，`warnings` 为 0。

## Subproblems

1. `01-sample-review-and-style-lock.md` - 审阅 10 篇样稿，锁定文字与配图规则，确认样稿是否冻结 - status: verified
2. `02-scene-outline-90.md` - 为 N011–N100 设计 90 个不重复的选题与图片要点 - status: verified
3. `03-draft-90-notes.md` - 按批次写标题和正文，填入 `notes.csv` - status: verified
4. `04-produce-90-images.md` - 按选定方案制作 90 张独立配图 - status: verified
5. `05-search-cases-and-qa.md` - 完成 `search-cases.csv`，做全文冲突检查与随机抽查 - status: verified
6. `06-package-and-validate.md` - 打 `campus-notes-v1.zip` 并用仓库校验器验证 - status: verified
7. `07-delivery.md` - 把 ZIP 交付给用户，不执行导入 - status: verified

## Dependencies

- 02 依赖 01 的风格确认和“样稿是否冻结”的决定。
- 03 依赖 02 的 90 行选题表。
- 04 依赖 02 的图片要点；配图方案已定为 B，不再阻塞。
- 05 依赖 03 和 04 全部完成，才能核对搜索词和图文对应。
- 06 依赖 05 通过。
- 07 依赖 06 通过，并且要确认交付方式。

## Recommended execution order

1. 先完成 01：和用户确认样稿风格、是否改动 N001–N010，以及 90 张图怎么做。
2. 写 02：先出选题表给用户扫一眼，避免写到一半发现撞题。
3. 写 03：按五个主题分批写，每批写完就检查字数和搜索词位置。
4. 做 04：图片可以和文字分批并行，但必须先确认视觉方向。
5. 做 05：搜索词审计完成后，再进入打包。
6. 做 06：打包并用仓库校验器验证。
7. 做 07：交付 ZIP 路径，导入留给用户。

## End-to-end verification

在仓库根目录执行：

```sh
docker compose up --build -d --wait
docker compose cp .local/campus-deliveries/campus-notes-v1.zip api:/tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import validate /tmp/campus-notes.zip
```

期望输出：

```json
{"notes": 100, "cases": 6, "warnings": []}
```

再手动检查：

- 打开 ZIP，第一层只能看到 `notes.csv`、`search-cases.csv`、`images/`。
- 随机抽 10 篇，对照标题、正文和图片，确认讲的是同一件事。
- 五类各 20 篇；N001–N010 与样稿一致；搜索词只出现在指定编号的指定字段。

## Decisions (2026-11-21)

1. **样稿**：按建议冻结 N001–N010，标题、正文、图片都不改。用户若后续要求，再单独开修复步骤。
2. **配图**：用户选择方案 B，制作统一风格的扁平插画，`image_source` 填“本人绘制”。先出 N011、N029、N065 三张试稿，确认视觉后再做剩余 87 张。
3. **交付**：默认交付本地路径 `.local/campus-deliveries/campus-notes-v1.zip`；邮件或网盘等发送渠道在交付时确认。
