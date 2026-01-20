from enum import Enum

class userType(Enum):
    customer = 1
    driver = 2

class intentCustome(Enum):
    #乘客端意图
    customToken = "优惠券咨询"
    customOrder = "订单咨询"
    customBasicService = "基础服务咨询"
    customAccount = "账户相关咨询"
    customPrivacy = "隐私与规则咨询"

class intentDriver(Enum):
    #司机端意图
    driverToken = "优惠券咨询"
    driverAuthen = "认证咨询"
    driverAcceptOrdeer = "接单问题咨询"
    driverOrder = "订单咨询"
    driverBasicService = "基础服务咨询"
