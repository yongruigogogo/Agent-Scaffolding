from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from zoneinfo import ZoneInfo
from Common.DBCommon.sqlLiteCom import getBase

class inputDetectionRes (getBase("chatHistory_db")):
    __tablename__ = "intentDetection"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    userId = Column(String(50), nullable=False)
    userInput = Column(String(500), nullable=False)
    isPassed = Column(Boolean, nullable=False)
    reason = Column(String(500), nullable=False)
    chatHistory = Column(String(2000))
    chatDate = Column(DateTime, default=lambda: datetime.now(ZoneInfo("UTC")), nullable=False)