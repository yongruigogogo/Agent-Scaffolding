import concurrent
import json
import os
import time
from typing import Optional, Dict
from json_repair import repair_json
from langchain_openai import ChatOpenAI
from Common.utils import getAbsolutePath, loadYmlFile, initLogger


class ModelFactory:
    def __init__(self,purpose:str = "common"):
        self.logger = initLogger(__name__)
        #读取配置文件
        configPath = getAbsolutePath("../Config/config.yml")
        config = loadYmlFile(configPath)
        #LLM模型的配置
        if purpose == "common":
            self.__llmApiKey = os.getenv("API_KEY_EXTERNAL")
            self.__baseURL = config["llm"]["base_url"]
            self.__modelName = config["llm"]["model_name"]
    def __getModel(self,stream:bool = False):
        return ChatOpenAI(model_name=self.__modelName,
                          openai_api_key=self.__llmApiKey,
                          openai_api_base=self.__baseURL,
                          streaming=stream)
    #调用模型
    def invoke(self,query:str,stream:bool=False):
        model = self.__getModel(stream)
        if stream:
            # 流式输出
            tokenIterator = model.stream(query)
            return tokenIterator
        else:
            return model.invoke(query)
    #超时自动重新调用
    def invokeRetry(self,query:str,stream:bool=False,maxRuntime:int = 300,maxRetryCount:int = 3,restTime:int = 20):
        model = self.__getModel(stream)
        def invokeWithRuntime():
            return model.invoke(query)
        if stream:
            # 流式输出
            tokenIterator = model.stream(query)
            self.logger.info(f"Calling the stream LLM API successfully.")
            return tokenIterator
        else:
            retryCount = 0
            while retryCount < maxRetryCount:
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(invokeWithRuntime)
                        # 超时抛异常TimeoutError
                        output = future.result(timeout=maxRuntime)
                        self.logger.info(f"Calling the LLM API successfully.Output: {output}")
                        return output
                except concurrent.futures.TimeoutError:
                    retryCount += 1
                    self.logger.warning(f"LLM call timed out!")
                    time.sleep(restTime)
                except Exception as e:
                    # 捕获其他异常
                    retryCount += 1
                    self.logger.warning(f"LLM call failed:{str(e)}")
                    time.sleep(restTime)
            self.logger.error(f"Reach max retry time!")
            raise Exception(f"Reach max retry time!")
    #返回json
    def invokeJson(self,query:str,maxRuntime:int = 300,maxRetryCount:int = 3,restTime:int = 20) -> Dict:
        model = self.__getModel()
        def invokeWithRuntime():
            return model.invoke(query)
        retryCount = 0
        while retryCount < maxRetryCount:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(invokeWithRuntime)
                    # 超时抛异常TimeoutError
                    output = future.result(timeout=maxRuntime)
                    jsonRepair = repair_json(output.content,ensure_ascii=False)
                    if len(jsonRepair.strip()) == 0:
                        self.logger.warning(f"Json parsing failed")
                        raise Exception(f"Json parsing failed")
                    jsonOutput = json.loads(jsonRepair)
                    self.logger.info(f"Calling the LLM API successfully.Output: {output}")
                    return jsonOutput
            except concurrent.futures.TimeoutError:
                retryCount += 1
                self.logger.warning(f"LLM call timed out!")
                time.sleep(restTime)
            except Exception as e:
                # 捕获其他异常
                retryCount += 1
                self.logger.warning(f"LLM call failed:{str(e)}")
                time.sleep(restTime)
        self.logger.error(f"Reach max retry time!")
        raise Exception(f"Reach max retry time!")
