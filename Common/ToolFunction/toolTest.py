import requests

from Common.utils import initLogger


def findNoUsePage(userId: int,page: int,limit: int):
    # return "用户有一张九折券可以用。"
    logger = initLogger(__name__)
    #前置条件模拟登录
    baseUrl = "http://localhost:8511"
    groupUrl = "/coupon/info"
    url = f"{baseUrl}{groupUrl}/findNoUsePage/{int(userId)}/{page}/{limit}"

    try:
        response = requests.get(url, timeout=10)
        #检查请求是否成功
        response.raise_for_status()
        result = response.json()
        respCode = result["code"]
        if respCode != 200:
            raise Exception(f"error response {respCode}")
        pageData = result.get("data")
        logger.info(f"Request success! \n {str(pageData)}")
        return str(pageData["records"])
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return "工具调用失败，不需要进一步重新调用，直接让用户自行查看即可。"

if __name__ == "__main__":
    findNoUsePage(1,1,100)