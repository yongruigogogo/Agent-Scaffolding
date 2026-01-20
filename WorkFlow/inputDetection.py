from datetime import datetime
from typing import TypedDict, List
from langgraph.graph import END
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph
from sqlalchemy import MetaData,Table,select

from Common.DBCommon.sqlLiteCom import getDbSession
from Common.Prompt.inputDetectionPrompt import semanticsDetectionPrompt
from Common.llmApiFactory import ModelFactory
from Common.utils import ACAutomaton, initLogger
from Model.Entity.inputDetectionRes import inputDetectionRes


class __conditionalState(TypedDict):
    userQuery: str  # 输入
    isDetectionPass: bool  #检测是否通过
    reason: str  #检测不通过的原因
    pipelineHistory: List #对话历史

model = ModelFactory()

#AC自动机敏感词检测
def __sensitiveWordDetection(state: __conditionalState) -> __conditionalState:
    logger = initLogger(__name__)
    userQuery = state["userQuery"]
    pipelineHistory = state["pipelineHistory"]
    #查违禁词
    sensitiveWords = []
    isDetectionPass = True
    reason = ""
    try:
        sqliteSession = next(getDbSession("sensitiveWord_db"))
        engine = sqliteSession.bind
        metadata = MetaData()
        target_table = Table(
            "sensitiveWords",  # 表名
            metadata,
            autoload_with=engine  # 自动从引擎加载表结构
        )
        query = select(target_table.c.word)
        result = sqliteSession.execute(query)
        wordList = result.scalars().all()
        sensitiveWords = [str(word) if word is not None else "" for word in wordList]
    except Exception as e:
        logger.error(f"Search sensitive words Failed! \n {e}")
    #初始化自动机
    acAutomaton = ACAutomaton()
    for word in sensitiveWords:
        acAutomaton.add_sensitive_word(word)
    acAutomaton.build_fail_pointer()
    matched = acAutomaton.match(userQuery)
    if len(matched) != 0:
        failedSentence = f"用户输入敏感度检测不通过。原因：包含违禁词{str(matched)}。"
        pipelineHistory.append(SystemMessage(failedSentence))
        isDetectionPass = False
        reason = failedSentence
    else:
        pipelineHistory.append(SystemMessage("用户输入敏感度检测--敏感词部分通过。"))
    return {
        "isDetectionPass": isDetectionPass,
        "reason": reason,
        "pipelineHistory" :pipelineHistory
    }

#LLM语义检测
def __semanticsDetection(state: __conditionalState) -> __conditionalState:
    userQuery = state["userQuery"]
    pipelineHistory = state["pipelineHistory"]
    detectionDict = model.invokeJson(semanticsDetectionPrompt.format(userInput = userQuery))
    isDetectionPass = detectionDict["detectionAns"]
    reason = detectionDict["reason"]
    pipelineHistory.append(SystemMessage(semanticsDetectionPrompt.format(userInput = userQuery)))
    pipelineHistory.append(AIMessage(str(detectionDict)))
    return {"isDetectionPass": isDetectionPass,
        "reason": reason,
        "pipelineHistory" :pipelineHistory}

def __buildConditionalAgent():
    graphBuilder = StateGraph(__conditionalState)
    graphBuilder.add_node("sensitiveWordDetection",__sensitiveWordDetection)
    graphBuilder.add_node("semanticsDetection", __semanticsDetection)
    def isPassed(state: __conditionalState) -> str:
        isDetectionPass = state["isDetectionPass"]
        if isDetectionPass:
            return "semanticsDetection"
        else:
            return END
    graphBuilder.set_entry_point("sensitiveWordDetection")
    graphBuilder.add_conditional_edges(
        source = "sensitiveWordDetection",
        path = isPassed
    )
    graphBuilder.add_edge("sensitiveWordDetection",END)
    conditionalAgent = graphBuilder.compile()
    return conditionalAgent

def inputDetection(userId:int,input:str) -> inputDetectionRes:
    logger = initLogger(__name__)
    detectionRes = inputDetectionRes()
    detectionRes.userId = str(userId)
    detectionRes.userInput = input
    agent = __buildConditionalAgent()
    iniInput = {
        "userQuery": input,
        "isDetectionPass": True,
        "reason": "",
        "pipelineHistory": []
    }
    result = agent.invoke(iniInput)
    detectionRes.reason = result["reason"]
    detectionRes.chatHistory = str(result["pipelineHistory"])
    detectionRes.isPassed = result["isDetectionPass"]
    try:
        sqliteSession = next(getDbSession("chatHistory_db"))
        sqliteSession.add(detectionRes)
        sqliteSession.commit()
        sqliteSession.refresh(detectionRes)
    except Exception as e:
        logger.error(f"DataBase Save Failed! \n {e}")
    logger.info(f"Intent Recognition Complete. Id:{detectionRes.id},Time:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return detectionRes