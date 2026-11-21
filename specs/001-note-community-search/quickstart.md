# 启动与验收

## 运行示例社区

在仓库根目录运行 `docker compose up --build -d --wait`。浏览器访问 [本地首页](http://127.0.0.1:8080)。账号 `lune` 和 `kai` 的示例密码均为 `notebook-demo`。API 启动时自动应用 Alembic 迁移并装载初始图文，重复启动会保留用户对种子笔记的编辑。

用两个独立浏览器会话分别登录。让甲发布一篇新的带图笔记，乙刷新首页后点开并收藏。作者改标题后刷新详情，再试新旧搜索词。首次创建索引时，搜索需要等待 worker 完成投递和刷新。

## 复现搜索故障

1. 搜索一个不存在的词，确认页面显示“没有找到相关笔记”。执行 `docker compose stop search`，再搜同一个词，页面应显示“搜索暂时不可用，请稍后再试”。
2. 在搜索停机期间发布笔记并连续改名两次。另取一篇原本可搜到的笔记，先编辑再删除。首页和详情仍能反映已提交的写入，原详情链接在删除后返回 404。
3. 执行 `docker compose start search`。待索引可查询后，搜最终标题，确认旧标题和已删笔记消失。`docker compose logs worker` 可查看相应的事件和版本。
4. 要复查一次旧更新，用 `docker compose exec worker python -m app.worker event NOTE_ID VERSION` 取得事件 ID，将参数占位符换成实际整数。运行 `docker compose exec worker python -m app.worker replay EVENT_ID`，再执行 `docker compose exec worker python -m app.worker refresh`。搜索最终标题，检查旧任务没有改变结果。

## 完整自动化验收

需要 Docker Compose、Python 3.12、Node.js 22 和 Chromium。激活 Python 虚拟环境后，从根目录运行：

```sh
python -m pip install -r backend/requirements-dev.txt
cd frontend
npm ci
npx playwright install chromium
cd ..
python scripts/verify.py
```

Linux 环境缺少浏览器系统库时，安装命令使用 `npx playwright install --with-deps chromium`。验收固定使用独立的 `rednote-test` 项目和数据卷，默认网页端口 18085、MySQL 端口 13316，可通过 `TEST_WEB_PORT` 和 `TEST_MYSQL_PORT` 调整。脚本构建五个服务，运行 MySQL 业务测试、真实搜索故障与重放测试、前端构建和浏览器流程。搜索验收记录实际耗时，统一等待上限为 30 秒。

完成后单独停止测试环境：

```sh
docker compose -p rednote-test -f compose.yaml -f compose.test.yaml stop
```

## 继续使用 Spec Kit

该功能目录是 `specs/001-note-community-search`。在 PowerShell 中运行以下命令检查规格、计划与任务输入：

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/001-note-community-search'
./.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks
```
