"""Regenerate the standalone DOCX ingestion fixture with python-docx."""

from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt


OUTPUT = Path(__file__).with_name("接入样本_DOCX.docx")


def main() -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.3)
    section.bottom_margin = Cm(2.3)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    normal = document.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(7)

    document.add_paragraph("DOCX 接入样本 处理记录与来源定位", style="Title")
    document.add_paragraph(
        "样本编号：DOCX-B2。本文是专为文档解析、标题、列表、表格和来源字段设计的虚构业务样本；不属于系统技术知识资料或正式题库。"
    )

    document.add_heading("处理规则", level=1)
    document.add_paragraph(
        "项目代号为海桐-29。接收文件后，处理员先核对文件标记 DOCX-B2；标记一致才将记录状态设为 received。完成字段抽取后，记录状态为 indexed。若文件标记不一致，记录状态为 rejected，且不进入索引。"
    )
    document.add_heading("操作次序", level=1)
    for item in [
        "读取文件标记 DOCX-B2 并保存原始文件名。",
        "核对项目代号海桐-29 与文件标记。",
        "字段抽取成功后记录 indexed 和处理时间。",
    ]:
        document.add_paragraph(item, style="List Number")

    document.add_heading("状态对照", level=1)
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "状态"
    table.rows[0].cells[1].text = "含义"
    for status, meaning in [
        ("received", "文件标记已核对，等待抽取"),
        ("indexed", "字段抽取完成并记录索引"),
        ("rejected", "文件标记不一致，不进入索引"),
    ]:
        row = table.add_row()
        row.cells[0].text = status
        row.cells[1].text = meaning

    document.add_heading("检索提示", level=1)
    document.add_paragraph(
        "提问“海桐-29 的文件标记不一致会进入索引吗？”时，预期回答为不会，状态为 rejected。来源应指向本 DOCX 样本的“处理规则”或“状态对照”片段。"
    )
    document.add_paragraph(
        "上述项目代号和流程均为测试数据。命中样本只说明解析和检索行为，不说明真实业务系统已实现该流程。"
    )
    document.save(OUTPUT)


if __name__ == "__main__":
    main()
