import importlib
import os
import sys
from typing import Dict, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from Common.utils import initLogger, getAbsolutePath, loadYmlFile

##用的时候初始化好
#数据库别名 路径
DB_CONFIG: Dict[str, str] = {}
#数据库引擎
ENGINE_MAP: Dict[str, create_engine] = {}
#会话
SESSION_MAP: Dict[str, sessionmaker] = {}
#模型基类
BASE_MAP: Dict[str, declarative_base] = {}
#调试模式
DEBUG_MODE = False

#Db初始化
def initSqlite():
    logger = initLogger(__name__)
    configPath = getAbsolutePath("../Config/config.yml")
    config = loadYmlFile(configPath)
    dbList = config["sqlite"]["db_name"]
    for dbAlias in dbList:
        DB_CONFIG[dbAlias] = getAbsolutePath(f"../DBFile/{dbAlias}.db")
        __initEachDb(dbAlias)
    #加载Model中对应的table
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
        spec.loader.exec_module(module)  # 执行模块代码（此时实例会被创建）
    for dbAlias in dbList:
        __createAllTables(dbAlias)

#初始化各个数据库
def __initEachDb(dbAlias: str) -> Tuple[declarative_base, sessionmaker]:
    logger = initLogger(__name__)
    #初始化指定别名的数据库（创建引擎、会话类、模型基类）
    # 若已初始化，直接返回缓存的基类和会话类
    if dbAlias in BASE_MAP and dbAlias in SESSION_MAP:
        return BASE_MAP[dbAlias], SESSION_MAP[dbAlias]
    if dbAlias not in DB_CONFIG:
        logger.error(f"Database '{dbAlias}' Can't Find Config!")
        raise KeyError(f"Database '{dbAlias}' Can't Find Config!")
    # 1. 获取数据库连接 URL
    db_path = DB_CONFIG[dbAlias]
    db_url = f"sqlite:///{db_path}"

    # 2. 创建引擎（存入引擎映射表）
    engine = create_engine(
        db_url,
        echo=DEBUG_MODE,
        pool_size=20,  # 连接池大小
        max_overflow=50  # 最大溢出连接数
    )
    ENGINE_MAP[dbAlias] = engine

    # 3. 创建该数据库专属的模型基类（存入基类映射表）
    base = declarative_base()
    BASE_MAP[dbAlias] = base

    # 4. 创建会话类（存入会话映射表）
    session_cls = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    SESSION_MAP[dbAlias] = session_cls
    logger.info(f"Initializing database {dbAlias} successfully!")
    return base, session_cls

#获取会话实例
def getDbSession(dbAlias: str):
    if dbAlias not in DB_CONFIG:
        __initEachDb(dbAlias)
    session_cls = SESSION_MAP[dbAlias]
    dbSession = session_cls()
    try:
        yield dbSession #返回生成器，next()触发了
    except Exception as e:
        dbSession.rollback()
        logger = initLogger(__name__)
        logger.error(f"Database session error: {e}")
        raise
    finally:
        dbSession.close()

def __createAllTables(db_alias: str):
    logger = initLogger(__name__)
    #创建数据库中所有表
    if db_alias not in BASE_MAP or db_alias not in ENGINE_MAP:
        __initEachDb(db_alias)
    base = BASE_MAP[db_alias]
    engine = ENGINE_MAP[db_alias]
    base.metadata.create_all(engine)  # 创建所有绑定该基类的模型表
    table_names = list(base.metadata.tables.keys())
    if table_names:
        table_names_str = ", ".join(table_names)
        logger.info(f"Create tables for {db_alias} successfully! Table names: {table_names_str}")

def getBase(db_alias: str):
    """延迟获取模型基类"""
    if db_alias not in BASE_MAP:
        if db_alias in DB_CONFIG:
            __initEachDb(db_alias)
        else:
            initSqlite()
    return BASE_MAP[db_alias]
