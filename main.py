from Common.DBCommon.sqlLiteCom import initSqlite
from RpcServe.serve import serve

#程序入口，初始化需要的模块
if __name__ == '__main__':
    initSqlite()
    serve()