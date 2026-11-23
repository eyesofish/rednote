# Subproblem 5: 定稿搜索答案表并做全文质检

## 1. Goal

把 `search-cases.csv` 定稿为 5 组成对搜索词加 1 个零匹配词，并确认每个词在全表只出现在登记的标题或正文里，没有第三篇误用。

## 2. Why this step exists

搜索演示依赖精确命中。仓库校验器会逐词扫描 100 篇标题和正文，要求“标题命中集合”和“仅正文命中集合”与答案表完全一致；多一篇、少一篇都会拒绝导入。这个检查必须在打包前单独做一遍，方便定位问题。

## 3. Files involved

- `.local/campus-authoring/build/campus-notes-v1/search-cases.csv` - 最终答案表，6 行。
- `.local/campus-authoring/build/campus-notes-v1/notes.csv` - 100 篇标题和正文，是被扫描的对象。
- `.local/campus-authoring/check_copy.py` - 03 建的临时检查脚本；本步骤扩展搜索词审计部分。
- `backend/app/campus_pack.py` - `_read_cases` 是搜索词规则的权威实现，遇到歧义以此为准。

## 4. Exact changes

1. 把 `search-cases.csv` 写成：

```csv
query,title_id,body_only_id
雨天通勤,N005,N006
雪地观鲸,,
错题索引,N011,N012
模拟群面,N029,N030
隔夜燕麦,N065,N066
周末集市,N083,N084
```

2. 逐词扫描 100 篇的 `title` 和 `body`，确认：
   - 标题包含该词的编号集合 = `{title_id}`。
   - 正文包含该词、且标题不含该词的编号集合 = `{body_only_id}`。
   - 其他 98 篇的标题和正文都不包含该连续短语。
3. 零匹配词“雪地观鲸”在 100 篇标题和正文中 0 次。
4. 如果发现第三篇误用，回到 03 改正文，不要通过换搜索词来绕过；换词也要重新跑全表审计。
5. 随机抽 10 篇（每类 2 篇），逐篇检查标题、正文、图片是否讲同一件物品；抽到的问题记录编号并回到 03/04 修。

## 5. Out of scope

- 不写新正文（只修冲突）。
- 不重新制作全部图片（只补或换不合格的）。
- 不打包 ZIP。
- 不导入数据库。

## 6. Done condition

- `search-cases.csv` 恰好 6 行：5 组各有两个不同编号，1 个零匹配行两个编号为空。
- 5 个查询词各自只命中登记的标题 1 篇和仅正文 1 篇。
- “雪地观鲸”0 次。
- 随机 10 篇图文对应，没有明显错位。
- 五类各 20 篇，N001–N100 唯一。

## 7. Verification

运行：

```sh
python .local/campus-authoring/check_copy.py --search
```

脚本对每个查询词输出：标题命中编号、仅正文命中编号、期望编号，以及是否一致。期望输出 6 行全部为 `OK`。

再人工确认：

- `search-cases.csv` 用 UTF-8 打开，中文没有乱码。
- 五个查询词都是连续的 2–6 字短语，没有空格、标点或换行。
- 抽 10 篇对照 `images/`，确认图文一致。

## 8. Expected output

定稿的 `search-cases.csv`，以及一份“6 个搜索词全部通过”的检查结果。若修过正文，`notes.csv` 同步更新。

## 9. Notes for the next step

06 打包时直接使用定稿的两张 CSV 和 `images/`。仓库校验器会再跑一遍同样的搜索规则，作为第二道保险。

## 10. Risks or ambiguity

- 搜索是子串匹配，不是分词匹配。“模拟群面”出现在“模拟群面试”里也会命中；审计时要看实际连续字符串。
- 修搜索冲突可能影响正文长度，改完要重新检查 80–200 字。
- 如果仓库里已有其它笔记也含这些词，导入后的搜索验收可能多出站内 ID；任务单允许在演示库验收，或换更有区分度的词。本步骤只保证交付包内部无冲突。
