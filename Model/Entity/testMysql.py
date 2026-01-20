from sqlalchemy import Column,Integer,String,Text

from Common.DBCommon.mysqlCom import getBase


class testMysql (getBase("db1")):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # MySQL需要指定长度
    bio = Column(Text, nullable=True)
