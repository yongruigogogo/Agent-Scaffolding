import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
from concurrent import futures
import grpc
from Common.utils import initLogger
from Model.Enums.intentEnum import userType
import agentService_pb2
import agentService_pb2_grpc
from WorkFlow.decisionAgent import decisionAgent
from WorkFlow.inputDetection import inputDetection
from WorkFlow.intenRecognition import intentRecognition


class agentServiceServicer(agentService_pb2_grpc.agentServiceServicer):
    #实现接口方法
    def getUserInfo(self, request, context):
        # request：客户端传递的实例
        userId = request.userId
        query = request.query
        type = userType(request.userType)
        # agent执行
        inputDetection(userId, query)
        intentRecognitionRes = intentRecognition(type,query,str(userId))
        if intentRecognitionRes.isItentClearly:
            decisionRes =  decisionAgent({"userId": userId}, intentRecognitionRes.userInput, intentRecognitionRes.outPut, "")
            agentAnswer = decisionRes.finalAnswer
        else:
            agentAnswer = intentRecognitionRes.outPut
        #输入输出的历史持久化操作还没做
        if agentAnswer and len(agentAnswer) != 0:
            return agentService_pb2.agentResponse(
                code = 200,
                message = "",
                data = agentAnswer,
            )
        else:
            return agentService_pb2.agentResponse(
                code=201,
                message="Agent Execution Failed",
                data="",
            )
def serve():
    logger = initLogger(__name__)
    # 创建 gRPC 服务器（使用多线程处理请求）
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
    # 注册自定义的服务实现到服务器
    agentService_pb2_grpc.add_agentServiceServicer_to_server(agentServiceServicer(), server)
    # 绑定端口（格式：[::]:端口号，支持 IPv4/IPv6）
    server.add_insecure_port("[::]:50051")
    # 启动服务器
    logger.info("gRPC server started on port 50051...")
    server.start()
    # 保持服务器运行（阻塞主线程）
    server.wait_for_termination()

if __name__ == "__main__":
    serve()