import json
from typing import List
import numpy as np
from Common.utils import initLogger, normalizeVectors, getEmbedding, getAbsolutePath
import faiss
from Model.Enums.intentEnum import userType, intentCustome, intentDriver


def getSimilarIntents(query:str,user:userType,count:int) -> List[intentCustome|intentDriver]:
    logger = initLogger(__name__)
    queryEmbedding, successReturn = getEmbedding(query)
    if not successReturn:
        logger.error("Embedding Failed!")
        return None
    if user == userType.customer:
        dataUrl = "../Rag/Dataset/intentDataCustom.jsonl"
    elif user == userType.driver:
        dataUrl = "../Rag/Dataset/intentDataDriver.jsonl"
    texts = []
    rawIntent = []
    ans  = []
    with open(getAbsolutePath(dataUrl), 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                # 解析json数据
                json_data = json.loads(line.strip())
                emb = np.array(json_data['embedding'], dtype=np.float32)
                texts.append(emb)
                rawIntent.append(json_data['intent'])
            except json.JSONDecodeError as e:
                logger.error("Parsing dataset file Failed!")
    doc_embeddings = np.array(texts, dtype=np.float32)
    doc_embeddings = normalizeVectors(doc_embeddings)  # 归一化文档向量
    embedding_dim = doc_embeddings.shape[1]
    index = faiss.IndexFlatIP(embedding_dim)
    # 添加文档向量到索引
    index.add(doc_embeddings)
    query = queryEmbedding
    query = np.array(query, dtype=np.float32)
    query = query.reshape(1, -1)
    scores, indices = index.search(query, k=count)
    indicesList = indices.tolist()[0]
    for indece in indicesList:
        ans.append(intentCustome(rawIntent[indece]) if user == userType.customer else intentDriver(rawIntent[indece]))
    return ans