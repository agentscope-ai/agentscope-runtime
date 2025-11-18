# -*- coding: utf-8 -*-
"""
PDF Excel Sandbox - 支持PDF解析(含OCR)和Excel操作的自定义沙箱

提供的工具:
- PaddleOCR官方MCP: 深度学习OCR, PP-StructureV3表格识别, 文档布局分析
- Excel MCP: Excel读取和写入操作
- Filesystem MCP: 文件复制和管理

沙箱特性:
- 混合语言环境: Node.js + Python
- PaddleOCR: 百度官方OCR引擎（中文识别准确率领先）
- UV工具链: 高性能Python包管理
"""
from typing import Optional
from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox

# 沙箱类型标识
PDF_EXCEL_SANDBOX_TYPE = "pdf_excel"


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-pdf-excel"),
    sandbox_type=PDF_EXCEL_SANDBOX_TYPE,
    security_level="medium",
    timeout=300,  # PaddleOCR深度学习模型可能耗时，设置5分钟超时
    description="PDF Excel Sandbox with PaddleOCR (Official MCP) and Excel MCP tools",
    volumes={  # 🔑 定义固定的volumes映射
        "/home/wym/workspace/agents/agentscope/agents-runtime/shared_files/uploads": "/shared_inputs",
        "/home/wym/workspace/agents/agentscope/agents-runtime/shared_files/agent_outputs": "/shared_outputs",
    },
)
class PDFExcelSandbox(Sandbox):
    """
    PDF Excel Sandbox类

    提供的MCP工具:
    1. PDF Reader MCP (Python + FastMCP):
       - read_pdf_text: 提取PDF文本内容
       - extract_pdf_images: 批量导出图像
       - read_pdf_with_ocr: 结合OCR识别图像中的文字
       - get_pdf_info: 获取元数据和统计信息
       - analyze_pdf_structure: 分析内容分布

    2. Excel MCP (Python + UV):
       - read_excel_template: 读取Excel模版结构
       - write_excel_data: 将数据写入Excel文件
       - (更多工具见Excel MCP文档)

    OCR能力:
    - 引擎: Tesseract OCR
    - 支持语言: 英语(eng), 中文简体(chi_sim), 中文繁体(chi_tra)
    - 性能优化: 自动跳过小于50x50像素的图像

    使用方式:
    通过@SandboxRegistry.register装饰器，Runtime自动识别:
    - sandbox_type="pdf_excel" → 使用镜像runtime-sandbox-pdf-excel
    - 装饰器自动添加到SandboxType枚举
    - 所有使用此类型的Agent自动共享同一个容器池（由Runtime管理）

    注意事项:
    - PDF OCR处理可能耗时，建议配置合理的timeout
    - 大型PDF文件建议分页处理
    - Excel操作需要提供正确的文件路径映射
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """
        初始化PDF Excel Sandbox

        Args:
            sandbox_id: 沙箱ID（可选）
            timeout: 超时时间（秒）
            base_url: 远程沙箱服务器URL（可选）
            bearer_token: 认证令牌（可选）
        """
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType(PDF_EXCEL_SANDBOX_TYPE),  # 🔑 关键：使用字符串创建枚举值
        )
