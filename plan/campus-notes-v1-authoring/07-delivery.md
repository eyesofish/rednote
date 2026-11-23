# Subproblem 7: 交付 ZIP

## 1. Goal

把通过校验的 `campus-notes-v1.zip` 交给用户，说明文件位置和内容，不执行导入。

## 2. Why this step exists

用户明确说“导入我来处理”。交付这一步只负责把正确的包递到用户手上，并留下可复核的信息，避免又改内容导致包和校验结果不一致。

## 3. Files involved

- `.local/campus-deliveries/campus-notes-v1.zip` - 最终交付包。
- `.local/campus-authoring/build/campus-notes-v1/` - 工作副本，保留用于后续修改和复跑。
- `content/campus/OPERATOR.md` - 用户导入时的命令参考；交付说明里可以引用，但不要替用户执行。

## 4. Exact changes

1. 确认 ZIP 的修改时间晚于最后一次内容修改时间。
2. 记录 ZIP 的 SHA-256 和文件大小，方便用户核对。
3. 默认把绝对路径发给用户：

```text
D:\Github\rednote\.local\campus-deliveries\campus-notes-v1.zip
```

4. 如果用户选择邮件或网盘，再用对应的 MCP 工具发送；发送前确认渠道和收件人。
5. 交付说明写清：
   - 包内是 100 篇、五个主题各 20 篇。
   - 两张 CSV 在 ZIP 根目录，图片在 `images/`。
   - 已通过 `app.campus_import validate`，`warnings` 为空。
   - 导入命令参考 `content/campus/OPERATOR.md`，由用户执行。

## 5. Out of scope

- 不导入、不 verify、不写数据库。
- 不修改包内容。
- 不把包提交到 git，除非用户明确要求。

## 6. Done condition

用户确认收到 ZIP，或已拿到可访问的本地路径/下载链接；交付说明包含校验结果和文件位置。

## 7. Verification

- 重新打开 ZIP，确认第一层是 `notes.csv`、`search-cases.csv`、`images/`。
- 随机解压 3 张图片，确认能离线打开。
- 对比 SHA-256 与交付说明一致。
- 确认没有把工作副本、选题表、HTML 预览误打进包。

## 8. Expected output

一个可交付的 `campus-notes-v1.zip` 路径（或发送记录），以及简短的交付说明。

## 9. Notes for the next step

没有下一步。用户导入后如果反馈某几篇要改，先更新 `notes.csv`/图片，再重跑 05 和 06，生成新的 ZIP；不要直接改已交付的 ZIP。

## 10. Risks or ambiguity

- “发我”可能指邮件、微信、网盘或本地路径。默认给本地路径，发送前先问清楚渠道。
- 如果用户已经导入过旧包，新包同编号内容必须保持一致，否则导入会报错；交付说明里要提醒这一点。
- `.local/` 在 `.gitignore` 里，不会被提交；如果用户希望包进入仓库，需要另说。
