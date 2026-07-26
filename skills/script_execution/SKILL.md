---
name: script_execution
description: 生成测试脚本、执行并生成结果报告
---
以下为测试脚本执行的提示流程

# 测试脚本工作流程
该技能必须在以下场景下才允许使用，禁止禁止在以下场景下使用该技能：当用户明确要求生成，然后执行测试脚本时。

## 前置条件
1. 查看用户上传的附件获取接口文档或前端结构信息，如果没有，请求用户上传信息。
2. 确认目标为后端 API 或 Web 前端，否则拒绝

## 执行流程
1. 用 **Write** 工具在当前会话输出目录(见系统提示词中 `{{SESSION_DIR}}`)生成脚本
   - 必须使用 Playwright 同步 API(`from playwright.sync_api import sync_playwright`)
   - 独立 Python 脚本(无 pytest/unittest)，每个用例 = 普通函数 + assert
   - 脚本中所有字符串必须使用纯 ASCII 字符(仅英文和标点)
   - 脚本输出信息时(例如 print)使用英文
   - 通过 Bash 执行 `python test_runner.py`
2. 最多 3 轮修错重试，失败则向用户报告
   - 可能遇到的不可抗力错误：
     - 测试的网页或api由于网络原因出现加载超时情况
     - 测试的网页由于前端结构变化导致脚本无法找到对应元素
3. 如果执行成功，**必须按以下顺序调用两个工具，不可跳过任意一步**：
   a. 先调 `problem_parser`，将 Bash 输出 + 脚本源码作为 `task_description` 传入
      → `problem_parser` (将原始测试结果转换成结构化的 xlsx 报告模板)
   b. 再将 `problem_parser` 的输出作为 `generation_instruction`，调 `call_file_generator` 生成 xlsx 报告文件
      → `call_file_generator` 需要结构化数据才能生成合法的 xlsx，纯文字 Markdown 会导致校验失败
   c. 生成的文档必须放置在系统提示词中 `{{SESSION_DIR}}` 目录下

## 规则
- 执行流程期间禁止验证环境(例如检查playwright是否安装，或检查输出文件夹是否存在等等)，直接执行
- Bash 命令必须使用 Windows 语法(dir、move、type、mkdir)
