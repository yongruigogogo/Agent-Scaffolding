import grpc

from RpcServe import agentService_pb2_grpc, agentService_pb2


# 调用 gRPC 服务
def get_user_info(user_id):
    # 1. 与服务端建立连接（insecure_channel：无加密连接，生产环境建议用 secure_channel）
    with grpc.insecure_channel("localhost:50051") as channel:
        # 2. 创建客户端存根（Stub）
        stub = agentService_pb2_grpc.agentServiceStub(channel)
        # 3. 构造请求对象
        request = agentService_pb2.systemRequest(userId=user_id,userType = 1,query = "我有哪些优惠券能用")
        try:
            # 4. 调用服务端接口（同步调用，对应简单 RPC）
            response = stub.getUserInfo(request)
            # 5. 处理响应结果
            print(f"{response.data}")
        except grpc.RpcError as e:
            # 捕获并处理 gRPC 异常
            print(f"Error: {e.code()}, {e.details()}")

if __name__ == "__main__":
    # 调用服务，查询 ID=1 的用户信息
    get_user_info(1)
    # 测试不存在的用户 ID
    # get_user_info(3)