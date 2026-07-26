---
name: incremental_modification
description: 对已生成的文件进行增量修改
---
以下为增量修改已生成文件时的提示流程

# 增量修改流程
该技能必须在以下场景下才允许使用，禁止在其他场景下使用该技能：当用户提出对已有文件进行修改的明确需求时。

## 二进制文件(.xlsx / .docx / .pdf)
- **小改**(格式、细节、单文件)：
  使用 `call_file_generator`，设置 `is_modification=true`，传入 `previous_content_json`
- **需求变更**(新增文件类型、测试范围扩大)：
  先调用 `call_problem_parser` 重新分析，再调用 `call_batch_file_generator`生成新文件

## 非二进制文件(.py / .js / .md / .sql / .txt 等)
先使用 `FormatRead` 读取原有文件内容，再使用 `Write` 工具结合用户需求进行修改
注意：读取 DOCX/XLSX/PDF 时使用 FormatRead 而非 Read

# 重要规则
- 禁止在生成文件过程前后验证文件输出地址是否存在，验证生成文件是否存在，文件生成后即为流程结束
