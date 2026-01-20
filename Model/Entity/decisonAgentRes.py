from Common.DBCommon.sqlLiteCom import getBase
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from zoneinfo import ZoneInfo

class decisionAgentRes (getBase("chatHistory_db")):
    __tablename__ = "decisionAgent"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    userId = Column(String(50), nullable=False)
    userInput = Column(String(500), nullable=False)
    observation = Column(String(5000), nullable=False) #思考与执行的结果的List
    finalAnswer = Column(String(500), nullable=False)
    chatHistory = Column(String(2000))
    chatDate = Column(DateTime, default=lambda: datetime.now(ZoneInfo("UTC")), nullable=False)