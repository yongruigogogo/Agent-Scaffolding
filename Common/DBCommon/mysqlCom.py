import importlib
import os
import sys
from typing import Dict, Any, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from Common.utils import initLogger, getAbsolutePath, loadYmlFile

# 数据库配置信息
DB_CONFIG: Dict[str, Dict[str, Any]] = {}
# 数据库引擎
ENGINE_MAP: Dict[str, create_engine] = {}
# 会话
SESSION_MAP: Dict[str, sessionmaker] = {}
# 模型基类
BASE_MAP: Dict[str, declarative_base] = {}
# 调试模式
DEBUG_MODE = False

#Db初始化
def initMysql():
    logger = initLogger(__name__)
    configPath = getAbsolutePath("../Config/config.yml")
    config = loadYmlFile(configPath)
    dbConfigs = config["mysql"]["databases"]
    #存储数据库配置
    for dbAlias, dbConfig in dbConfigs.items():
        DB_CONFIG[dbAlias] = dbConfig
        __initEachDb(dbAlias)
    # 加载Model中对应的table
    modelDir = getAbsolutePath("../Model")
    if not os.path.exists(modelDir):
        logger.error(f"Model dir {modelDir} not exists.Initialization failing!")
        raise FileNotFoundError(f"Model dir {modelDir} not exists.Initialization failing!")
    for fileName in os.listdir(modelDir):
        filePath = os.path.join(modelDir, fileName)
        if not os.path.isfile(filePath):
            continue
        if not fileName.endswith(".py"):
            continue
        module_name = os.path.splitext(os.path.basename(filePath))[0]
        # 动态加载模块
        spec = importlib.util.spec_from_file_location(module_name, filePath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        # 为每个数据库创建表
    for db_alias in dbConfigs.keys():
        __createAllTables(db_alias)

#初始化单个数据库
def __initEachDb(dbAlias: str) -> Tuple[declarative_base, sessionmaker]:
    logger = initLogger(__name__)
    if dbAlias in BASE_MAP and dbAlias in SESSION_MAP:
        return BASE_MAP[dbAlias], SESSION_MAP[dbAlias]

    if dbAlias not in DB_CONFIG:
        logger.error(f"Database '{dbAlias}' Can't Find Config!")
        raise KeyError(f"Database '{dbAlias}' Can't Find Config!")
    dbConfig = DB_CONFIG[dbAlias]
    # 构建MySQL连接URL
    dbUrl = (
        f"mysql+pymysql://{dbConfig.get('user', 'root')}:"
        f"{dbConfig.get('password', '')}@"
        f"{dbConfig.get('host', 'localhost')}:"
        f"{dbConfig.get('port', 3306)}/"
        f"{dbConfig.get('database', dbAlias)}"
    )
    #添加连接参数
    charset = dbConfig.get('charset', 'utf8mb4')
    poolRecycle = dbConfig.get('pool_recycle', 3600)
    poolPrePing = dbConfig.get('pool_pre_ping', True)
    dbUrl = f"{dbUrl}?charset={charset}"
    # 创建引擎
    engine = create_engine(
        dbUrl,
        echo=DEBUG_MODE,
        pool_size=dbConfig.get('pool_size', 20),  # 连接池大小
        max_overflow=dbConfig.get('max_overflow', 50),  # 最大溢出连接数
        pool_recycle=poolRecycle,  # 连接回收时间（秒）
        pool_pre_ping=poolPrePing,  # 连接前ping检查
        pool_timeout=dbConfig.get('pool_timeout', 30),  # 获取连接超时时间
        connect_args={
            'connect_timeout': dbConfig.get('connect_timeout', 10)
        }
    )
    ENGINE_MAP[dbAlias] = engine
    # 创建该数据库专属的模型基类
    base = declarative_base()
    BASE_MAP[dbAlias] = base
    # 创建会话类
    sessionCls = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    SESSION_MAP[dbAlias] = sessionCls
    logger.info(
        f"initializing Database '{dbAlias}'  Successfully！Connect to {dbConfig.get('host', 'localhost')}:{dbConfig.get('port', 3306)}/{dbConfig.get('database', dbAlias)}")
    return base, sessionCls

#获取数据库会话
def getDbSession(dbAlias: str):
    if dbAlias not in SESSION_MAP:
        __initEachDb(dbAlias)
    session_cls = SESSION_MAP[dbAlias]
    dbSession = session_cls()
    try:
        yield dbSession
    except Exception as e:
        dbSession.rollback()
        logger = initLogger(__name__)
        logger.error(f"Database session error: {e}")
        raise
    finally:
        dbSession.close()

#创建数据库中所有表
def __createAllTables(dbAlias: str):
    logger = initLogger(__name__)
    if dbAlias not in BASE_MAP or dbAlias not in ENGINE_MAP:
        __initEachDb(dbAlias)
    base = BASE_MAP[dbAlias]
    engine = ENGINE_MAP[dbAlias]
    try:
        base.metadata.create_all(engine)
        table_names = list(base.metadata.tables.keys())
        if table_names:
            table_names_str = ", ".join(table_names)
            logger.info(f"Database '{dbAlias}' table creates Successfully！Table Name: {table_names_str}")
    except Exception as e:
        logger.error(f"Database '{dbAlias}' table creates failed: {e}")
        raise

def getBase(db_alias: str) -> declarative_base:
    """延迟获取模型基类"""
    if db_alias not in BASE_MAP:
        if db_alias in DB_CONFIG:
            __initEachDb(db_alias)
        else:
            initMysql()
    return BASE_MAP[db_alias]
