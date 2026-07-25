# -*- coding: utf-8 -*-
"""FileGenerationContext - 追踪每轮文件生成的内容数据

因为 xlsx/docx/pdf 等二进制文件无法"先读后改"，
所以在上下文中保存每轮生成的 content JSON 数据。
用户要求修改时，直接修改 JSON 数据后重新生成文件。
"""


class FileGenerationContext:
    """追踪每一轮文件生成的内容数据，支持增量修改"""

    def __init__(self):
        self.records: dict[str, dict] = {}
        # records 结构:
        # {
        #     "output/test_cases.xlsx": {
        #         "file_type": "xlsx",
        #         "content": { "sheets": [...] },   # 原始 content JSON
        #     },
        #     "output/mock_sms.py": {
        #         "file_type": "py",
        #         "content": { "code": "..." },
        #     },
        # }

    def record(self, output_path: str, file_type: str, content: dict) -> None:
        """记录一次文件生成的数据"""
        self.records[output_path] = {
            "file_type": file_type,
            "content": content,
        }

    def get_content(self, output_path: str) -> dict | None:
        """获取某个文件的原始 content 数据，用于修改"""
        record = self.records.get(output_path)
        return record["content"] if record else None

    def get_file_type(self, output_path: str) -> str | None:
        """获取某个文件的类型"""
        record = self.records.get(output_path)
        return record["file_type"] if record else None

    def list_files(self) -> list[str]:
        """列出所有已跟踪的文件路径"""
        return list(self.records.keys())

    def get_summary(self) -> str:
        """生成当前上下文摘要，供协调者使用"""
        if not self.records:
            return "暂无已生成文件"
        lines = ["当前已生成文件及内容结构："]
        for path, info in self.records.items():
            content_preview = self._preview_content(info["content"])
            lines.append(f"- {path} ({info['file_type']}): {content_preview}")
        return "\n".join(lines)

    def _preview_content(self, content: dict) -> str:
        """生成 content 的简要预览"""
        if "sheets" in content:
            sheet_names = [s.get("name", "?") for s in content["sheets"]]
            return f"Excel, sheets={sheet_names}"
        elif "code" in content:
            return f"代码文件, {len(content['code'])} 字符"
        elif "title" in content:
            return f"文档, 标题='{content['title']}'"
        elif "statements" in content:
            return f"SQL, {len(content['statements'])} 条语句"
        else:
            return "其他类型"
