from langchain_core.tools import BaseTool

from medivault.agents.tools.consultation_tools import record_consultation
from medivault.agents.tools.medicine_tools import (
    check_interactions,
    search_documents,
    search_medicines,
)
from medivault.agents.tools.patient_tools import (
    get_patient_history,
    get_patient_record,
    search_memory,
    search_patients,
)
from medivault.agents.tools.sales_tools import get_sales_summary

TOOLS: list[BaseTool] = [
    search_medicines,
    search_documents,
    check_interactions,
    search_patients,
    get_patient_record,
    get_patient_history,
    search_memory,
    record_consultation,
    get_sales_summary,
]

TOOL_MAP = {tool.name: tool for tool in TOOLS}
