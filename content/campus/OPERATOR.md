# 收件人如何验收与导入

发给作者的是 `campus-classmate-kit.zip`。收回的是 `campus-notes-v1.zip`，其根目录包含两张 CSV 和 `images/`。仓库另附一份可直接试跑的十篇样稿 `campus-notes-pilot.zip`。

## 检查样稿

解压交接包，打开 `样稿预览.html`，可在离线时阅读全部图文。若要重新打包源码或生成可单独打开的 HTML 文件，在仓库根目录执行：

```sh
python scripts/build_campus_kit.py
```

三个输出位于 `.local/campus-deliveries/`。正式包另抽十篇，对照主题与配图检查写作质量。确认复用的十篇样稿已经定稿后再导入目标库。

## 导入和重复验收

在仓库根目录启动项目，复制样稿 ZIP 到 API 容器。以下命令会把样稿发布为 `lune` 的笔记：

```sh
docker compose up --build -d --wait
docker compose cp content/campus/downloads/campus-notes-pilot.zip api:/tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import validate /tmp/campus-notes.zip --stage pilot
docker compose exec -T api python -m app.campus_import import /tmp/campus-notes.zip --stage pilot --author lune
docker compose exec -T api python -m app.campus_import verify /tmp/campus-notes.zip --stage pilot
```

检查 `warnings` 中的字数、比例或体积提示。首次全新导入的结果应为 `created=10` 和 `reused=0`，再次执行应为 `created=0` 和 `reused=10`。输出中的 `ids` 把 N001 等包编号对应到站内笔记 ID。可以在首页查看这十条图文，也可以搜索“雨天通勤”确认 N005 排在 N006 前面。

收齐 100 篇后，换成以下命令。正式包默认使用 `final` 校验规则；同一份样稿已入库且内容一致时，只新增其余 90 篇。

```sh
docker compose cp campus-notes-v1.zip api:/tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import validate /tmp/campus-notes.zip
docker compose exec -T api python -m app.campus_import import /tmp/campus-notes.zip --author lune
docker compose exec -T api python -m app.campus_import verify /tmp/campus-notes.zip
```

导入保存笔记、图片与索引待办，整包在一次事务中提交。若某编号已属于其他作者、已删除或已改稿，命令会报出编号并回滚本次新增。对照当前笔记与包内容处理差异，再重试。分类、图片来源和文件名保存在 CSV，站内仍使用现有的图文笔记结构。

搜索验收最多等待 30 秒，核对实际返回的站内 ID 和完整顺序。如果社区里另有笔记使用相同关键词，输出会显示额外命中的 ID。可在独立演示库运行精确数量验收，或在正式定稿前改用更有区分度的词。索引不可用时，命令会报告搜索故障；服务恢复后重新执行 `verify` 即可。
