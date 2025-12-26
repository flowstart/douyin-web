"""
快递100 API 客户端
"""
import hashlib
import json
from typing import Dict, Any, Optional
import httpx

from app.config import get_settings

settings = get_settings()

# 快递公司编码映射（来源：快递100官方编码表）
# 包含常用快递公司及其别名映射
COMPANY_CODE_MAP = {
    # 顺丰
    "顺丰速运": "shunfeng",
    "顺丰快递": "shunfeng",
    "顺丰": "shunfeng",
    "顺丰快运": "shunfengkuaiyun",
    "顺丰冷链": "shunfenglengyun",
    # 中通
    "中通快递": "zhongtong",
    "中通": "zhongtong",
    "中通快运": "zhongtongkuaiyun",
    "中通国际": "zhongtongguoji",
    "中通冷链": "ztocc",
    # 圆通
    "圆通速递": "yuantong",
    "圆通快递": "yuantong",
    "圆通": "yuantong",
    "圆通国际": "yuantongguoji",
    # 韵达
    "韵达快递": "yunda",
    "韵达": "yunda",
    "韵达快运": "yundakuaiyun",
    # 申通
    "申通快递": "shentong",
    "申通": "shentong",
    "申通国际": "stosolution",
    # 极兔
    "极兔速递": "jtexpress",
    "极兔快递": "jtexpress",
    "极兔": "jtexpress",
    "极兔国际": "jet",
    # 京东
    "京东物流": "jd",
    "京东快递": "jd",
    "京东": "jd",
    "京东快运": "jingdongkuaiyun",
    # 邮政/EMS
    "邮政快递包裹": "youzhengguonei",
    "邮政快递": "youzhengguonei",
    "邮政": "youzhengguonei",
    "EMS": "ems",
    "邮政电商标快": "youzhengdsbk",
    "邮政标准快递": "youzhengbk",
    "EMS物流": "emswuliu",
    "EMS包裹": "emsbg",
    "EMS-国际件": "emsguoji",
    # 德邦
    "德邦快递": "debangkuaidi",
    "德邦": "debangkuaidi",
    "德邦物流": "debangwuliu",
    # 百世
    "百世快递": "huitongkuaidi",
    "百世": "huitongkuaidi",
    "百世快运": "baishiwuliu",
    "百世国际": "baishiguoji",
    # 菜鸟
    "菜鸟速递": "danniao",
    "菜鸟": "danniao",
    "菜鸟大件": "cainiaodajian",
    "菜鸟国际": "cainiaoglobal",
    # 天天快递
    "天天快递": "tiantian",
    "天天": "tiantian",
    # 其他常用快递
    "跨越速运": "kuayue",
    "安能快运": "annengwuliu",
    "安能快递": "ane66",
    "壹米滴答": "yimidida",
    "日日顺物流": "rrs",
    "宅急送": "zhaijisong",
    "苏宁物流": "suning",
    "货拉拉物流": "huolalawuliu",
    # 国际快递
    "UPS": "ups",
    "DHL": "dhl",
    "DHL-中国件": "dhl",
    "DHL-全球件": "dhlen",
    "FedEx": "fedex",
    "FedEx-国际件": "fedex",
    "联邦快递": "lianbangkuaidi",
    "TNT": "tnt",
    "USPS": "usps",
}


class KD100Client:
    """快递100 API 客户端"""
    
    def __init__(self, customer: str = None, key: str = None):
        """
        初始化快递100客户端
        
        Args:
            customer: 快递100 customer ID，不传则从环境变量读取
            key: 快递100 API key，不传则从环境变量读取
        """
        self.api_url = settings.kd100_api_url
        self.key = key or settings.kd100_key
        self.customer = customer or settings.kd100_customer
        self._client = httpx.AsyncClient(timeout=10.0)
    
    def _get_company_code(self, company_name: str) -> str:
        """
        根据快递公司名称获取编码
        
        Args:
            company_name: 快递公司名称，如"申通快递"
        
        Returns:
            快递公司编码，如"shentong"
        """
        # 先尝试精确匹配
        if company_name in COMPANY_CODE_MAP:
            return COMPANY_CODE_MAP[company_name]
        
        # 模糊匹配
        for name, code in COMPANY_CODE_MAP.items():
            if name in company_name or company_name in name:
                return code
        
        # 默认返回原名称的小写
        return company_name.lower().replace("快递", "").replace("速递", "")
    
    def _generate_sign(self, param: str) -> str:
        """
        生成签名
        sign = MD5(param + key + customer)
        """
        sign_str = f"{param}{self.key}{self.customer}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
    
    async def query(
        self, 
        tracking_number: str, 
        company_name: str
    ) -> Dict[str, Any]:
        """
        查询物流轨迹
        
        Args:
            tracking_number: 物流单号
            company_name: 快递公司名称
        
        Returns:
            物流轨迹信息
        """
        company_code = self._get_company_code(company_name)
        
        # 构建请求参数
        param = json.dumps({
            "com": company_code,
            "num": tracking_number,
        }, separators=(",", ":"))
        
        sign = self._generate_sign(param)
        
        # 发送请求
        response = await self._client.post(
            self.api_url,
            data={
                "customer": self.customer,
                "sign": sign,
                "param": param,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        
        result = response.json()
        return result
    
    def parse_status(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析物流状态
        
        Args:
            result: 快递100 API返回结果
        
        Returns:
            解析后的状态信息
        """
        # 状态码说明
        # state（快递100）：
        # - 常见：0-在途 1-揽收 2-疑难 3-签收 4-退签 5-派件 6-退回 7-转投
        # - 兼容扩展：301/302/303/304 也视为“已签收”（不同产品线/接口可能返回扩展码）
        state = result.get("state", "")
        signed_states = {"3", "301", "302", "303", "304"}
        status_map = {
            "0": {"status": "in_transit", "desc": "在途"},
            "1": {"status": "collected", "desc": "已揽收"},
            "2": {"status": "problem", "desc": "疑难"},
            "3": {"status": "signed", "desc": "已签收"},
            "301": {"status": "signed", "desc": "已签收"},
            "302": {"status": "signed", "desc": "已签收"},
            "303": {"status": "signed", "desc": "已签收"},
            "304": {"status": "signed", "desc": "已签收"},
            "4": {"status": "rejected", "desc": "退签"},
            "5": {"status": "delivering", "desc": "派件中"},
            "6": {"status": "returning", "desc": "退回"},
            "7": {"status": "transferred", "desc": "转投"},
        }
        
        status_info = status_map.get(str(state), {"status": "unknown", "desc": "未知"})
        
        # 获取最新轨迹
        data = result.get("data", [])
        latest_track = data[0] if data else None
        
        return {
            "is_signed": str(state) in signed_states,
            "status": status_info["status"],
            "status_desc": status_info["desc"],
            "latest_time": latest_track.get("time") if latest_track else None,
            "latest_context": latest_track.get("context") if latest_track else None,
            "track_count": len(data),
        }
    
    async def check_signed(
        self, 
        tracking_number: str, 
        company_name: str
    ) -> Dict[str, Any]:
        """
        检查是否已签收
        
        Args:
            tracking_number: 物流单号
            company_name: 快递公司名称
        
        Returns:
            签收状态信息
        """
        try:
            result = await self.query(tracking_number, company_name)
            
            if result.get("message") == "ok":
                return self.parse_status(result)
            else:
                return {
                    "is_signed": False,
                    "status": "error",
                    "status_desc": result.get("message", "查询失败"),
                    "latest_time": None,
                    "latest_context": None,
                    "track_count": 0,
                }
        except Exception as e:
            return {
                "is_signed": False,
                "status": "error",
                "status_desc": str(e),
                "latest_time": None,
                "latest_context": None,
                "track_count": 0,
            }
    
    async def close(self):
        """关闭客户端连接"""
        await self._client.aclose()


def parse_express_info(express_str: str) -> Dict[str, str]:
    """
    解析快递信息字符串
    
    格式: "物流单号-快递公司,商品信息-商品ID,数量;"
    例如: "770291786060549-申通快递,商品名称-3788410999938351943,1;"
    
    Args:
        express_str: 快递信息字符串
    
    Returns:
        {"tracking_number": "xxx", "company_name": "xxx"}
    """
    if not express_str or express_str == "-":
        return {"tracking_number": "", "company_name": ""}
    
    try:
        # 提取第一个逗号前的部分
        first_part = express_str.split(",")[0]
        # 按-分割
        parts = first_part.split("-")
        if len(parts) >= 2:
            return {
                "tracking_number": parts[0].strip(),
                "company_name": parts[1].strip(),
            }
    except Exception:
        pass
    
    return {"tracking_number": "", "company_name": ""}

