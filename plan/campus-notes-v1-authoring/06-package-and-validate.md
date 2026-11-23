# Subproblem 6: 打包并用仓库校验器验证

## 1. Goal

把 `notes.csv`、`search-cases.csv` 和 `images/` 打包成根目录平铺的 `campus-notes-v1.zip`，再用仓库自带的最终阶段校验规则验证通过。

## 2. Why this step exists

任务单明确要求“选中 `campus-notes-v1` 文件夹里面的三项压缩”，ZIP 第一层就要看到两张 CSV。仓库的 `app.campus_import validate` 会检查编号、主题分布、字段、字数警告、图片格式/尺寸/唯一性、搜索词命中，是本项目最可靠的验收方式。

## 3. Files involved

- `.local/campus-authoring/build/campus-notes-v1/notes.csv` - 定稿的 100 行。
- `.local/campus-authoring/build/campus-notes-v1/search-cases.csv` - 定稿的 6 行。
- `.local/campus-authoring/build/campus-notes-v1/images/` - 100 张图片。
- `.local/campus-authoring/package_pack.py` - 本步骤新建的打包脚本；只用标准库 `csv`、`zipfile`、`pathlib`。
- `.local/campus-deliveries/campus-notes-v1.zip` - 最终交付包。
- `backend/app/campus_import.py` - `validate` 子命令的入口。
- `compose.yaml` - 启动 API 容器；`docker compose cp` 需要它。

## 4. Exact changes

1. 新建 `.local/campus-authoring/package_pack.py`：
   - 从 `build/campus-notes-v1/` 读两张 CSV 和 `images/`。
   - 用 `csv.reader` 读入、`csv.DictWriter` 重新写出为 UTF-8 BOM，`lineterminator="\n"`，避免 Excel 中文乱码。
   - 用 `zipfile.ZipFile(..., "w", ZIP_DEFLATED)` 写入，arcname 固定为 `notes.csv`、`search-cases.csv`、`images/Nxxx.ext`，分隔符统一用 `/`，不要把 `campus-notes-v1/` 前缀带进去。
   - 不写入临时文件、`.DS_Store`、源 HTML 或选题表。
   - 输出到 `.local/campus-deliveries/campus-notes-v1.zip`。
2. 运行打包脚本，生成 ZIP。
3. 启动 API 容器并校验：

```sh
docker compose up --build -d --wait
docker compose cp .local/campus-deliveries/campus-notes-v1.zip api:/tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import validate /tmp/campus-notes.zip
```

4. 如果输出里有 warnings（正文长度、4:3、500 KB），逐条按编号修 `notes.csv` 或图片，回到对应步骤，重新打包再验证，直到 `warnings` 为空数组。

## 5. Out of scope

- 不执行 `import` 或 `verify`；用户自己导入。
- 不改内容（发现问题回到 03/04/05）。
- 不把 ZIP 复制进 `content/campus/downloads/`，除非用户要求提交到仓库。

## 6. Done condition

- ZIP 存在，大小合理。
- ZIP 内文件清单只有 `notes.csv`、`search-cases.csv`、`images/…`，没有 `campus-notes-v1/` 外层目录。
- `validate` 输出 `{"notes": 100, "cases": 6, "warnings": []}`。
- 解压后两张 CSV 是 UTF-8，中文正常，`images/` 有 100 个文件。

## 7. Verification

```sh
python .local/campus-authoring/package_pack.py
docker compose up --build -d --wait
docker compose cp .local/campus-deliveries/campus-notes-v1.zip api:/tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import validate /tmp/campus-notes.zip
```

期望：

```json
{"notes": 100, "cases": 6, "warnings": []}
```

再手动检查 ZIP 第一层：

```sh
python -c "import zipfile; print('\n'.join(zipfile.ZipFile('.local/campus-deliveries/campus-notes-v1.zip').namelist()[:5]))"
```

期望前几项能看到 `notes.csv`、`search-cases.csv`、`images/N001.webp` 等，不应出现 `campus-notes-v1/notes.csv`。

## 8. Expected output

`.local/campus-deliveries/campus-notes-v1.zip`，`validate` 无错误、无警告。

## 9. Notes for the next step

07 只负责交付和路径说明。ZIP 校验通过后不要再改内容；一旦改动，必须重新打包并重跑 `validate`。

## 10. Risks or ambiguity

- Docker 未启动或镜像未构建时，`validate` 会失败；这是环境问题，不是包内容问题。可先确认 `docker compose ps`。
- 用 PowerShell `Compress-Archive` 有可能写出反斜杠路径或多余目录；优先用 Python `zipfile` 明确控制 arcname。
- CSV 若被 Excel 重新保存，可能变成 GBK 或删掉 BOM；打包脚本应始终从工作副本重新编码。
- 如果用户之前导入过样稿，正式包导入时会复用 N001–N010；本步骤只校验包本身，不检查数据库状态。
