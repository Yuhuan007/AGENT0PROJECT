# 录屏脚本（照此操作即可覆盖全部提交要点）

目标：3~5 分钟录屏，证明使用**真实 LLM API**跑通 Agent 全流程。建议用 OBS / Windows 自带 Xbox Game Bar（Win+G）录制终端窗口。

---

## 镜头 0：开场（10 秒）
- 展示项目目录结构：`ls agent/` 或在 IDE 侧边栏展示文件树。
- 一句话旁白：这是从零实现、无框架依赖的 Mini Agent，使用智谱 GLM 真实 API。

## 镜头 1：证明真实 API 配置（15 秒）
- 打开 `.env`，展示 `LLM_MODEL_ID=glm-4-flash`、`LLM_BASE_URL=https://open.bigmodel.cn/...`。
- 强调：真实 API，非 mock。

```bash
cd D:\Documents\Agent0Project\agent
```

## 镜头 2：快速演示 —— 真实 LLM 跑 4 个场景（60 秒）
```bash
python demo_mini_agent.py
```
- 录下：计算 (100+50)*2、查北京天气、搜索、多工具协作。
- 重点停留在终端输出的 `🔧 调用工具` 和 `✅ 工具结果`，证明工具真正被调用。

## 镜头 3：基础测试套件（40 秒）
```bash
python test_mini_agent.py
```
- 录下 6 个测试依次 ✅ 通过。

## 镜头 4：全部测试聚合（60 秒）
```bash
python run_all_tests.py
```
- 拉到最后的汇总表：`总计: 17 项 | ✅ 通过 17`。

## 镜头 5：Context 管理 + 追问（30 秒）
```bash
python test_context.py
```
- 重点展示“带工具的追问”：先算 200+300=500，再追问“除以5”得 100，证明记忆与追问。

## 镜头 6：异常处理 + 执行 trace（30 秒）
```bash
python test_error_and_trace.py
```
- 展示 8 项通过，特别是 LLM 失败降级、工具异常隔离、trace 记录成功/失败。

## 镜头 7：多窗口独立会话（30 秒，可选）
```bash
python test_multi_window.py
```
- 展示窗口1 / 窗口2 待办完全隔离的验证结果。

## 收尾（10 秒）
- 回到 `run_all_tests.py` 的全绿汇总画面定格。

---

## 提交清单对照

| 要求 | 对应材料 | 状态 |
|------|----------|------|
| 使用真实 LLM API | `.env`（glm-4-flash）+ 镜头 1/2 | ✅ |
| 代码链接 | 整个 `agent/` 目录（推 Git 仓库后附链接） | 待你推仓库 |
| 终端/网页操作录屏 | 按本脚本录制镜头 0~7 | 待录制 |
| README（运行方式/系统设计/memory 召回与放置） | `README_SUBMISSION.md` | ✅ |
| AI Prompt 与问题解决记录 | `AI_PROMPT_LOG.md` | ✅ |

## 推 Git 仓库获取代码链接（示例）
```bash
cd D:\Documents\Agent0Project
git init
# 建议先加 .gitignore 忽略 __pycache__/ 和 .env（.env 含 key，勿上传公开仓库）
git add agent/
git commit -m "Mini Agent Runtime 提交"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```
> 注意：`.env` 含真实 API Key。若仓库公开，务必先把 `.env` 加入 `.gitignore`，改为提交一份 `.env.example`。
