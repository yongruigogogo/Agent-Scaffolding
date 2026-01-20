from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from Common.DBCommon.sqlLiteCom import BASE_MAP, getBase


class intentRecognitionRes(getBase("chatHistory_db")):
    __tablename__ = "intentRecognition"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True,nullable=False)
    userId = Column(String(50), nullable=False)
    userInput = Column(String(500), nullable=False)
    successFinish = Column(Boolean, nullable=False)
    isItentClearly = Column(Boolean)
    outPut = Column(String(300))
    chatHistory = Column(String(2000))
    chatDate = Column(DateTime, default=lambda: datetime.now(ZoneInfo("UTC")), nullable=False)

