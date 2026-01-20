import ast
from datetime import datetime
from typing import TypedDict, List, Any
from langgraph.graph import StateGraph,END
from Common.ToolFunction import toolTest
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy import MetaData,Table,select
from Common.DBCommon.sqlLiteCom import getDbSession
from Common.ToolFunction.toolRegistery import callAgentTool
from Common.llmApiFactory import ModelFactory
from Common.Prompt.decisionAgentPrompt import thinkingPrompt, toolUsingPrompt, paramSelectPrompt, toneAnalysisPrompt, \
    finishPrompt
from Common.utils import initLogger
from Model.Entity.decisonAgentRes import decisionAgentRes
from RpcServe import agentService_pb2


class __conditionalState(TypedDict):
    userQuery: str  # 输入
    userInfo: Any # 用户的信息
    intent: str  # 用户的意图
    thought: List # 思考
    action: List # 行动
    observation: List # react结果
    finalAnswer: str
    isFinish: str
    pipelineHistory: List  # 对话历史
    chatHistory: str #前几轮对话的对话历史

model = ModelFactory()

#推理思考过程
def __thinkStep(state: __conditionalState) -> __conditionalState:
    userQuery = state["userQuery"]
    observation = state["observation"]
    pipelineHistory = state["pipelineHistory"]
    thought = state["thought"]
    action = state["action"]
    chatHistory = state["chatHistory"]
    thinkigPrompt = thinkingPrompt.format(chatHistory = chatHistory, cleanedInput = userQuery, thoughtChain = str(observation))
    thinkingThoughtDict = model.invokeJson(thinkigPrompt)
    isFinish = thinkingThoughtDict["isEnd"]
    thought.append(thinkingThoughtDict["thoughtAns"])
    action.append(thinkingThoughtDict["action"])
    pipelineHistory.append(HumanMessage(thinkigPrompt))
    pipelineHistory.append(AIMessage(str(thinkingThoughtDict)))
    return {
        "thought": thought,
        "action": action,
        "isFinish": isFinish,
        "pipelineHistory": pipelineHistory
    }

#工具调用
def __toolUsing(state: __conditionalState) -> __conditionalState:
    logger = initLogger(__name__)
    userQuery = state["userQuery"]
    thought = state["thought"]
    action = state["action"]
    intent = state["intent"]
    observation = state["observation"]
    userInfo = state["userInfo"]
    pipelineHistory = state["pipelineHistory"]
    toolListFiltered = []
    #加载工具调用表
    try:
        sqliteSession = next(getDbSession("toolRegister_db"))
        engine = sqliteSession.bind
        metadata = MetaData()
        target_table = Table(
            "toolUsingTable",  # 表名
            metadata,
            autoload_with=engine  # 自动从引擎加载表结构
        )
        query = select(target_table)
        result = sqliteSession.execute(query)
        toolList = result.mappings().all() #返回字典list，列名:数值
        if len(toolList) == 0:
            raise ValueError("Don't find any tools in the table")
        for dict in toolList:
            intentList = ast.literal_eval(dict["intentList"])
            if intent in intentList:
                toolListFiltered.append(dict)
    except Exception as e:
        logger.error(f"Tool List search failed! \n {e}")
    #工具选择
    toolUsing = toolUsingPrompt.format(tools = str(toolListFiltered),cleanedInput = str(userQuery),
                                             thinkingAns = str(thought[-1]),action = str(action[-1]))
    toolUsingDict = model.invokeJson(toolUsing)
    pipelineHistory.append(HumanMessage(toolUsing))
    pipelineHistory.append(AIMessage(str(toolUsingDict)))
    #工具参数的选择
    paraList = None
    toolCapability = ""
    for toolDict in toolListFiltered:
        if toolDict["toolName"] == toolUsingDict["toolName"]:
            paraList = toolDict["inputPara"]
            toolCapability = toolDict["toolCapability"]
    paramSelect = paramSelectPrompt.format(tool = str(toolCapability),paraNameList = str(paraList), userInfo = str(userInfo))
    paramSelectDict = model.invokeJson(paramSelect)
    pipelineHistory.append(HumanMessage(paramSelect))
    pipelineHistory.append(AIMessage(str(paramSelectDict)))
    #工具调用
    callingAns = callAgentTool(toolUsingDict["toolName"],**paramSelectDict["paraList"])
    observation.append(f"推理思考的结果:{thought[-1]}。行动规划的结果:{action[-1]}。工具调用结果:调用了工具{toolUsingDict['toolName']}。选择该工具的理由:{toolUsingDict['reason']}。工具调用的结果:{callingAns}")
    return{
        "observation" : observation,
        "pipelineHistory" : pipelineHistory
    }

#生成最终结果
def __finishReAct(state: __conditionalState) -> __conditionalState:
    observation = state["observation"]
    pipelineHistory = state["pipelineHistory"]
    chatHistory = state["chatHistory"]
    intent = state["intent"]
    #聊天记录语气适配
    toneAnalysis = toneAnalysisPrompt.format(userInput = str(chatHistory))
    toneAnalysisDict = model.invokeJson(toneAnalysis)
    pipelineHistory.append(HumanMessage(toneAnalysis))
    pipelineHistory.append(AIMessage(str(toneAnalysisDict)))
    #用户意图语气适配,没做，写个注释意思意思
    #最终的结果
    finish = finishPrompt.format(pipelineAns = str(observation),tone = str(toneAnalysisDict["outputTone"]))
    finishDict = model.invokeJson(finish)
    pipelineHistory.append(HumanMessage(finish))
    pipelineHistory.append(AIMessage(str(finishDict)))
    return{
        "finalAnswer": finishDict["content"],
        "pipelineHistory": pipelineHistory
    }

def __buildConditionalAgent():
    graphBuilder = StateGraph(__conditionalState)
    graphBuilder.add_node("thinkStep",__thinkStep)
    graphBuilder.add_node("toolUsing",__toolUsing)
    graphBuilder.add_node("finishReAct",__finishReAct)
    def isReasoningEnd(state: __conditionalState) -> str:
        isFinish = state["isFinish"]
        if isFinish:
            return "finishReAct"
        else:
            return "toolUsing"
    graphBuilder.set_entry_point("thinkStep")
    graphBuilder.add_conditional_edges(
        source = "thinkStep",
        path = isReasoningEnd
    )
    graphBuilder.add_edge("toolUsing","thinkStep")
    graphBuilder.add_edge("finishReAct", END)
    conditionalAgent = graphBuilder.compile()
    return conditionalAgent

def decisionAgent(userInfo,userQuery:str,intent:str,dialogHistory:str) -> decisionAgentRes:
    logger = initLogger(__name__)
    decisionRes = decisionAgentRes()
    decisionRes.userId = userInfo["userId"]
    decisionRes.userInput = userQuery
    agent = __buildConditionalAgent()
    iniInput = {
        "userQuery": userQuery,
        "userInfo": userInfo,
        "intent": intent,
        "thought": [],
        "action": [],
        "observation": [],
        "finalAnswer": "",
        "isFinish": False,
        "pipelineHistory": [],
        "chatHistory": dialogHistory,
    }
    result = agent.invoke(iniInput)
    decisionRes.observation = str(result['observation'])
    decisionRes.finalAnswer = result['finalAnswer']
    decisionRes.chatHistory = str(result['pipelineHistory'])
    try:
        sqliteSession = next(getDbSession("chatHistory_db"))
        sqliteSession.add(decisionRes)
        sqliteSession.commit()
        sqliteSession.refresh(decisionRes)
    except Exception as e:
        logger.error(f"DataBase Save Failed! \n {e}")
    logger.info(
        f"Agent Complete Decisions. Id:{decisionRes.id},Time:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return decisionRes
