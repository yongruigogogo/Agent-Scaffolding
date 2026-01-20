from typing import Dict, Any

from Common.ToolFunction.toolTest import *
from Common.utils import initLogger

#工具注册表，哪些工具可以使用
TOOL_REGISTRY:Dict[str, Dict[str, Any]] = {
    "findNoUsePage":{
        "func":findNoUsePage,
        "description":"查询用户未使用的优惠券有哪些",
        "params": ["userId","page","limit"],
    }
}

#封装工具调用的核心函数
def callAgentTool(toolName:str, **kwargs) -> str:
    logger = initLogger(__name__)
    cleanToolName = toolName.strip().lower()
    matchedTool = None
    for toolId,toolMeta in TOOL_REGISTRY.items():
        if cleanToolName == toolId.lower():
            matchedTool = toolMeta
    if not matchedTool:
        logger.error("Tool not Exit!")
        return ""
    #校验参数
    missingParams = [kwargs.get(param) for param in matchedTool["params"] if param not in kwargs]
    if missingParams:
        logger.error(f"Missing params: {str(missingParams)}")
        return ""
    try:
        toolFunc = matchedTool["func"]
        result = toolFunc(**kwargs)
        logger.info(f"Tool use successfully! Result:{result}")
        return result
    except Exception as e:
        logger.info(f"Tool use Failed! \n {e}")
        return ""
