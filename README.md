# 页间 · Rednote

一个可以亲手做搜索故障实验的图文笔记社区。用一个账号发笔记，用另一个账号搜索和收藏。停掉 Elasticsearch 后仍可改标题、删笔记。搜索恢复后，可以重放旧编辑，检查已经删除的笔记会不会回来。

![页间操作演示：浏览校园笔记，搜索“雨天通勤”，查看标题命中和正文命中的排序，然后尝试一个没有结果的搜索词。](docs/rednote-demo.gif)

搜索“雨天通勤”，看标题命中的笔记如何排在仅正文命中的笔记前面。[下载演示视频（MP4，40 秒，中文字幕）](https://raw.githubusercontent.com/eyesofish/rednote/main/docs/rednote-demo.mp4)

## 在本地使用

安装带 Compose 的 Docker，在仓库根目录运行：

```sh
docker compose up --build -d --wait
```

用浏览器打开 [本地社区](http://127.0.0.1:8080)。首次启动会创建数据库、两个示例账号和两篇带原创插画的中文笔记。账号为 `lune`（阿月）和 `kai`（小凯），本地示例密码均为 `notebook-demo`。只把网页端口绑定到回环地址。已有数据随 Compose 卷保留，可用 `docker compose stop` 暂停。

在搜索框输入“美团”。《美团一面复盘》应排在只在正文提到美团的《周末面试笔记》前面。用 `lune` 登录可编辑原笔记。端口已被占用时，将环境变量 `WEB_PORT` 设为其他空闲端口再启动。

## 架构

Vue 3 页面通过同源 API 访问 FastAPI。MySQL 8.4 保存账号、笔记、图片和收藏。编辑和待同步快照在一次事务里提交。独立的 Python 进程把快照写入 Elasticsearch 9，版本号保证旧任务无法覆盖后来的编辑或删除。

| 你想做什么 | 入口 |
| --- | --- |
| 请同学制作 100 篇校园笔记 | [下载作者交接包](content/campus/downloads/campus-classmate-kit.zip) · [任务单](content/campus/BRIEF.md) |
| 将校园图文导入社区、检查搜索顺序 | [十篇样稿 ZIP](content/campus/downloads/campus-notes-pilot.zip) · [收件与导入手册](content/campus/OPERATOR.md) |
| 运行完整测试、复现停机和恢复 | [启动与验收手册](specs/001-note-community-search/quickstart.md) |
| 准备面试，画出一次改名的完整路径 | [一页架构取舍](docs/architecture.md) |
| 理解第一版的功能边界与验收标准 | [PRD](PRD.md) · [功能规格](specs/001-note-community-search/spec.md) |
| 沿 Spec Kit 查看技术决策与各部分任务 | [技术方案](specs/001-note-community-search/plan.md) · [任务清单](specs/001-note-community-search/tasks.md) |

开发代码位于 `backend/` 和 `frontend/`。服务编排在 `compose.yaml`，端到端验收入口是 `scripts/verify.py`。GitHub Actions 在 PR 和主分支执行自动化验收。
