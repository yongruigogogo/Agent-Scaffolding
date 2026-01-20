from datetime import datetime
from typing import TypedDict, List, Dict
from langchain_core.messages import SystemMessage, AIMessage
from Common.DBCommon.sqlLiteCom import getDbSession
from Common.Prompt.intentRecognitionPrompt import PreCleaningPrompt, featureExtractionPrompt, reQuestionPrompt
from Common.llmApiFactory import ModelFactory
from langgraph.graph import StateGraph,END
from Model.Entity.intentRecognitionRes import intentRecognitionRes
from Model.Enums.intentEnum import userType, intentCustome, intentDriver
from Common.utils import initLogger
from Rag.intentRecognitionRAG import getSimilarIntents

"""用于做意图识别的Agent"""

class __conditionalState(TypedDict):
    userQuery: str #输入
    userType: userType #用户类型
    cleanedDialog: str #冗余清洗
    queryQuestion: str #意图检索增强的查询
    intentPropotions: Dict[intentCustome | intentDriver, float] #不同意图的占比
    isItentClearly: bool #用户是否明确自己的意图
    outPut: str #结果输出
    pipelineHistory: List

model = ModelFactory()
customerDict: Dict[intentCustome, float] = {}
driverDict: Dict[intentDriver, float] = {}

def __initProportionDict():
    #初始化占比Dict
    for custom in intentCustome:
        customerDict[custom] = 0
    for driver in intentDriver:
        driverDict[driver] = 0
#对话清理
def __answerPreCleaning(state: __conditionalState) -> __conditionalState:
    userQuery = state["userQuery"]
    pipelineHistory = state["pipelineHistory"]
    if pipelineHistory is None:
        pipelineHistory = []
    cleanContentDict = model.invokeJson(PreCleaningPrompt.format(inputDialog = userQuery))
    pipelineHistory.append(SystemMessage(PreCleaningPrompt.format(inputDialog = userQuery)))
    pipelineHistory.append(AIMessage(str(cleanContentDict)))
    return {"cleanedDialog" : cleanContentDict["cleanDialog"],
            "userType": state["userType"],
            "pipelineHistory" : pipelineHistory}

#特征提取
def __featureExtraction(state: __conditionalState) -> __conditionalState:
    cleanedDialog = state["cleanedDialog"]
    pipelineHistory = state["pipelineHistory"]
    queryContentDict = model.invokeJson(featureExtractionPrompt.format(cleanedDialog = cleanedDialog))
    pipelineHistory.append(SystemMessage(featureExtractionPrompt.format(cleanedDialog = cleanedDialog)))
    pipelineHistory.append(AIMessage(str(queryContentDict)))
    return {"queryQuestion" : queryContentDict["queryContent"],
            "userType": state["userType"],
                "pipelineHistory" : pipelineHistory}

#RAG和意图分析
def __RAGandInentAnalysis(state: __conditionalState) -> __conditionalState:
    queryQuestion = state["queryQuestion"]
    pipelineHistory = state["pipelineHistory"]
    userType = state["userType"]
    #检索最相似的n条语句
    retrieveSum = 15
    propotionThreshold = 0.6
    isItentClearly = False
    retrieveAns = getSimilarIntents(queryQuestion,userType,retrieveSum)
    userDict = customerDict.copy() if userType == userType.customer else driverDict.copy()
    #统计意图占比
    for item in retrieveAns:
        userDict[item] += 1
    for key in userDict.keys():
        userDict[key] = userDict[key]/retrieveSum
    maxVal = max(userDict.values())
    if maxVal > propotionThreshold:
        isItentClearly = True
    return {"intentPropotions": userDict,
            "isItentClearly": isItentClearly,
            "pipelineHistory" : pipelineHistory}

#意图清晰
def __intentClear(state: __conditionalState) -> __conditionalState:
    pipelineHistory = state["pipelineHistory"]
    intentContent = max(state["intentPropotions"],key = lambda k:state["intentPropotions"][k]).value
    return {"outPut": intentContent,
            "pipelineHistory" : pipelineHistory}

#意图不清晰
def __intentNotClear(state: __conditionalState) -> __conditionalState:
    pipelineHistory = state["pipelineHistory"]
    reqeustionDict = model.invokeJson(reQuestionPrompt.format(inputDialog = state["cleanedDialog"],intentProportion = state["intentPropotions"]))
    pipelineHistory.append(SystemMessage(reQuestionPrompt.format(inputDialog = state["cleanedDialog"],intentProportion = state["intentPropotions"])))
    pipelineHistory.append(AIMessage(str(reqeustionDict)))
    return {"outPut": reqeustionDict["queryContent"],
            "pipelineHistory" : pipelineHistory}

def __buildConditionalAgent():
    graphBuilder = StateGraph(__conditionalState)
    graphBuilder.add_node("answerPreCleaning",__answerPreCleaning)
    graphBuilder.add_node("featureExtraction",__featureExtraction)
    graphBuilder.add_node("RAGandInentAnalysis",__RAGandInentAnalysis)
    graphBuilder.add_node("intentClear", __intentClear)
    graphBuilder.add_node("intentNotClear", __intentNotClear)

    def chooseOutputNode(state: __conditionalState) -> str:
        isItentClearly = state["isItentClearly"]
        if isItentClearly:
            return "intentClear"
        else:
            return "intentNotClear"
    graphBuilder.set_entry_point("answerPreCleaning")
    graphBuilder.add_edge("answerPreCleaning","featureExtraction")
    graphBuilder.add_edge("featureExtraction","RAGandInentAnalysis")
    graphBuilder.add_conditional_edges(
        source = "RAGandInentAnalysis",
        path = chooseOutputNode
    )
    graphBuilder.add_edge("intentClear", END)
    graphBuilder.add_edge("intentNotClear", END)
    conditionalAgent = graphBuilder.compile()
    return conditionalAgent

def intentRecognition(user:userType,queryContent:str,userId:str) -> intentRecognitionRes:
    __initProportionDict()
    logger = initLogger(__name__)
    #意图识别的最终结果
    intentRes = intentRecognitionRes()
    intentRes.userInput = queryContent
    intentRes.userId = userId
    agent = __buildConditionalAgent()
    iniInput = {
        "userQuery": queryContent,
        "userType": user,
        "cleanedDialog": "",
        "queryQuestion": "",
        "intentPropotions": {},  # 空字典
        "isItentClearly": True, # 默认用户意图不明确
        "outPut": "",
        "pipelineHistory": []    # 空列表
    }
    result = agent.invoke(iniInput)
    intentRes.successFinish = True
    if not result["isItentClearly"]:
        intentRes.isItentClearly = False
    else:
        intentRes.isItentClearly = True
    intentRecognitionRes.userInput = result["cleanedDialog"]
    intentRes.outPut = result["outPut"]
    intentRes.chatHistory = str(result["pipelineHistory"])
    #保存并返回
    try:
        sqliteSession = next(getDbSession("chatHistory_db"))
        sqliteSession.add(intentRes)
        sqliteSession.commit()
        sqliteSession.refresh(intentRes)
    except Exception as e:
        logger.error(f"DataBase Save Failed! \n {e}")
    logger.info(f"Intent Recognition Complete. Id:{intentRes.id},Time:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return intentRes
