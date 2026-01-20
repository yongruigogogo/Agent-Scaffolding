import inspect
import logging
import os
import sys
from collections import deque
from datetime import datetime
import yaml
import colorlog
import numpy as np
from huggingface_hub import snapshot_download
from sentence_transformers import SentenceTransformer


def getAbsolutePath(relativePath:str, base_dir=None) -> str:
    currentFilePath = os.path.abspath(__file__)
    currentDir = os.path.dirname(currentFilePath)
    useDir = base_dir if base_dir is not None else currentDir
    configPath = os.path.join(useDir, relativePath)
    configPath = os.path.normpath(configPath)
    return configPath

#读取yml文件
def loadYmlFile(path:str):
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

#日志系统
def initLogger(name=None):
    logger_name = name if name is not None else __name__
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    consoleFormatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'green',
            'INFO': 'green',
            'WARNING': 'yellow',
            'CRITICAL': 'red',
        }
    )

    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.DEBUG)
    consoleHandler.setFormatter(consoleFormatter)
    #持久化保存
    # 1. DEBUG级别专属文件
    logFilePathDebug = getAbsolutePath("../Log/debugLog.log")
    debugFileHandler = logging.FileHandler(
        filename=logFilePathDebug,  # DEBUG日志文件路径
        mode='a',  # 保留你原有追加模式
        encoding='utf-8'  # 保留你原有编码配置
    )
    debugFileHandler.setLevel(logging.DEBUG)  # 先设为最低级别，确保能捕获DEBUG
    debugFileHandler.setFormatter(formatter)  # 绑定你原有格式化器
    # 自定义过滤器：仅保留DEBUG级别日志
    class DebugFilter(logging.Filter):
        def filter(self, record):
            return record.levelno == logging.DEBUG

    debugFileHandler.addFilter(DebugFilter())  # 绑定DEBUG过滤器

    # 2. INFO级别专属文件：仅保存INFO日志（对应你的需求）
    logFilePathInfo = getAbsolutePath("../Log/infoLog.log")
    infoFileHandler = logging.FileHandler(
        filename=logFilePathInfo,  # INFO日志文件路径
        mode='a',
        encoding='utf-8'
    )
    infoFileHandler.setLevel(logging.INFO)  # 保留你原有级别配置
    infoFileHandler.setFormatter(formatter)

    # 自定义过滤器：仅保留INFO级别日志
    class InfoFilter(logging.Filter):
        def filter(self, record):
            return record.levelno == logging.INFO
    infoFileHandler.addFilter(InfoFilter())  # 绑定INFO过滤器
    # 3. 剩余级别（WARNING/ERROR/CRITICAL）合并文件：保存这三类日志
    logFilePathError = getAbsolutePath("../Log/errorLog.log")
    otherFileHandler = logging.FileHandler(
        filename=logFilePathError,  # 剩余级别日志文件路径
        mode='a',
        encoding='utf-8'
    )
    otherFileHandler.setLevel(logging.WARNING)  # 捕获≥WARNING级别日志
    otherFileHandler.setFormatter(formatter)

    # 自定义过滤器：仅保留WARNING/ERROR/CRITICAL级别
    class OtherFilter(logging.Filter):
        def filter(self, record):
            return record.levelno >= logging.WARNING

    otherFileHandler.addFilter(OtherFilter())  # 绑定过滤器，确保精准分流
    ##
    logger.addHandler(consoleHandler)
    logger.addHandler(debugFileHandler)
    logger.addHandler(infoFileHandler)
    logger.addHandler(otherFileHandler)
    return logger

def normalizeVectors(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)

def getEmbedding(content):
    logger = initLogger(__name__)
    try:
        model = SentenceTransformer(getAbsolutePath("../Rag/EmbeddingModel/"))
        embeddings = model.encode(content)
        return embeddings.tolist(), True
    except Exception as e:
        logger.error(e)
        return "", False

class ACNode:
    #AC自动机节点
    def __init__(self, char):
        self.char = char  # 当前节点存储的字符
        self.children = {}  # 子节点：key=字符，value=ACNode
        self.fail = None  # 失败指针（核心）
        self.is_end = False  # 是否是敏感词的结尾
        self.word = ""  # 如果是结尾，存储完整的敏感词


class ACAutomaton:
    """AC自动机核心类"""
    def __init__(self):
        self.root = ACNode("root")  # 根节点

    def add_sensitive_word(self, word):
        """向AC自动机中添加敏感词"""
        if not word or len(word) == 0:
            return
        current_node = self.root
        for char in word:
            # 如果字符不在子节点中，创建新节点
            if char not in current_node.children:
                current_node.children[char] = ACNode(char)
            # 移动到子节点
            current_node = current_node.children[char]
        # 标记为敏感词结尾，并存储完整词
        current_node.is_end = True
        current_node.word = word

    def build_fail_pointer(self):
        """构建失败指针（BFS遍历）"""
        queue = deque()
        # 根节点的失败指针为None，其子节点的失败指针指向根节点
        self.root.fail = None
        for child in self.root.children.values():
            child.fail = self.root
            queue.append(child)

        # BFS处理其他节点
        while queue:
            current_node = queue.popleft()

            # 遍历当前节点的所有子节点
            for char, child_node in current_node.children.items():
                # 初始化失败指针为根节点
                fail_node = current_node.fail

                # 向上回溯失败指针，直到找到匹配char的节点或根节点
                while fail_node is not None and char not in fail_node.children:
                    fail_node = fail_node.fail

                # 设置子节点的失败指针
                child_node.fail = fail_node.children[char] if (fail_node and char in fail_node.children) else self.root
                # 将子节点加入队列
                queue.append(child_node)

    def match(self, text):
        """
        匹配文本中的敏感词
        :param text: 用户输入的文本
        :return: 匹配到的敏感词列表（去重）
        """
        if not text or len(text) == 0:
            return []

        current_node = self.root
        matched_words = set()  # 用集合去重

        for char in text:
            # 匹配失败时，通过失败指针跳转
            while char not in current_node.children and current_node != self.root:
                current_node = current_node.fail

            # 如果当前字符在子节点中，移动到子节点；否则回到根节点
            current_node = current_node.children[char] if char in current_node.children else self.root

            # 检查当前节点及其失败指针链上是否有敏感词结尾
            temp_node = current_node
            while temp_node != self.root:
                if temp_node.is_end:
                    matched_words.add(temp_node.word)
                temp_node = temp_node.fail

        return list(matched_words)

if __name__ == '__main__':
    pass