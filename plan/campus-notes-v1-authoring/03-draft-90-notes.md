# Subproblem 3: 写 90 篇标题和正文

## 1. Goal

按 `outline.csv` 一行写一篇，把 N011–N100 的 `title` 和 `body` 填进 `notes.csv`，让 100 篇读起来像同一个人写的。

## 2. Why this step exists

这是交付包的主体内容。任务单要求 80–200 字、具体场景、避免同一句开场白套写整组；搜索演示还依赖标题和正文里精确出现的搜索词。把这一步独立出来，可以在做图之前先让用户审文字。

## 3. Files involved

- `.local/campus-authoring/build/campus-notes-v1/notes.csv` - 本步骤的工作副本。先从交接包复制 N001–N010 和全部 100 行模板，再填 N011–N100。
- `.local/campus-authoring/outline.csv` - 90 行选题表，按行提供场景、物品、细节和搜索词位置。
- `.local/campus-authoring/campus-classmate-kit/campus-notes-v1/notes.csv` - 只读样稿，用于对照语气和长度。
- `.local/campus-authoring/check_copy.py` - 本步骤新建的临时检查脚本，只用 Python 标准库 `csv` 和 `re`，不进入交付包。

## 4. Exact changes

1. 新建工作目录 `.local/campus-authoring/build/campus-notes-v1/`。
2. 复制交接包的 `notes.csv`、`search-cases.csv` 和 `images/N001.webp`…`N010.webp` 到工作目录。N001–N010 的六个字段保持原样，一个字符都不改。
3. 按主题分五批填写 N011–N100：
   - 第一批 N011–N028 校园自习。
   - 第二批 N029–N046 求职面试。
   - 第三批 N047–N064 租房通勤。
   - 第四批 N065–N082 宿舍做饭。
   - 第五批 N083–N100 周末活动。
4. 每篇按以下顺序写：
   - 先写标题：一句具体事件，12–24 字，包含关键物品或动作。
   - 再写正文：第一人称，一个场景，按时间推进；开头不要都用“今天/昨天/这周”。
   - 中间放一个不顺的细节和一个具体动作/数字。
   - 结尾落在可触摸的观察，不总结、不劝告。
   - 对照 `outline.csv` 的 `key_object`，确保正文里真的出现了这件物品。
5. 搜索词按 `keyword_slot` 放置：
   - N011 标题、N012 正文出现“错题索引”。
   - N029 标题、N030 正文出现“模拟群面”。
   - N065 标题、N066 正文出现“隔夜燕麦”。
   - N083 标题、N084 正文出现“周末集市”。
   - 这四个词在每个指定字段只出现一次；其他行不出现。
6. 求职类正文必须写明“模拟面试”“模拟群面”或“和同学练”，不得写成真实面试经历。
7. 正文里的引号使用中文引号“”；CSV 写入必须走 `csv` 模块，不要手工拼逗号。

写正文时可以启用 `humanize-chinese` 和 `avoid-ai-writing` 技能，重点检查：

- 是否有“首先/其次/最后”“在这个……的时代”“希望对你有帮助”这类套话。
- 是否每段都在解释道理，而不是写动作。
- 是否五篇里有三篇用同一个开头。

## 5. Out of scope

- 不制作图片，不改 `image_path` 和 `image_source`（04 再处理）。
- 不修改 `search-cases.csv`（05 再定稿）。
- 不打包 ZIP。
- 不改 N001–N010。

## 6. Done condition

- `notes.csv` 有 100 行数据，N001–N100 连续唯一。
- N011–N100 的 `title`、`body` 均非空。
- 每篇正文长度 80–200 字，目标 120–170 字。
- 100 个标题没有完全重复，也没有只换编号的模板句。
- 四个搜索词只出现在指定编号的指定字段；零匹配词“雪地观鲸”全文 0 次。
- N001–N010 与交接包逐字段一致。

## 7. Verification

运行临时检查脚本：

```sh
python .local/campus-authoring/check_copy.py
```

脚本至少要输出并检查：

- 总行数、每个主题的行数。
- 空标题/空正文的编号。
- 每篇正文长度，列出 80–200 之外的编号。
- 每个搜索词在标题和正文中的命中编号。
- 重复标题、重复开头前 8 个字。
- “雪地观鲸”命中次数。

再人工抽读 10 篇（每类 2 篇），检查是否像同一个人写的、是否有具体物品、结尾是否落在一个细节上。

## 8. Expected output

`.local/campus-authoring/build/campus-notes-v1/notes.csv`，100 行，N011–N100 标题和正文已填。

## 9. Notes for the next step

04 可以按 `outline.csv` 的 `image_brief` 和正文里的 `key_object` 做图。05 会重新跑一次搜索词审计，以最终 CSV 为准。

## 10. Risks or ambiguity

- 中文“字数”按字符数计算，标点也算。目标 120–170 字，给自己留出余量。
- 正文里出现英文逗号、引号或换行时，CSV 必须正确转义；用 `csv.DictWriter` 写入。
- Excel 另存可能改变编码或引号。不要用 Excel 打开工作副本；必须用表格软件时，导出 UTF-8。
- 90 篇一次写完容易语气趋同。按主题分批，每批写完先抽读再继续。
