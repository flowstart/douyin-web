"""
抖音开放平台 API 客户端
"""
import hashlib
import time
import json
from typing import Any, Dict, Optional
import httpx

from app.config import get_settings

settings = get_settings()


class DouyinClient:
    """抖音开放平台 API 客户端"""
    
    def __init__(self, access_token: str = ""):
        self.base_url = settings.douyin_api_base_url
        self.app_key = settings.douyin_app_key
        self.app_secret = settings.douyin_app_secret
        self.shop_id = settings.douyin_shop_id
        self.access_token = access_token
        self._client = httpx.AsyncClient(timeout=30.0)
    
    def _generate_sign(self, method: str, params: Dict[str, Any], timestamp: int) -> str:
        """
        生成请求签名
        签名规则：md5(app_secret + method + timestamp + param_json + app_secret)
        """
        param_json = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
        sign_str = f"{self.app_secret}{method}{timestamp}{param_json}{self.app_secret}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    
    async def _request(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送 API 请求
        
        Args:
            method: API 方法名，如 "order/searchList"
            params: 业务参数
        
        Returns:
            API 响应数据
        """
        params = params or {}
        timestamp = int(time.time())
        
        # 构建请求参数
        request_params = {
            "app_key": self.app_key,
            "method": method,
            "timestamp": str(timestamp),
            "v": "2",
            "sign_method": "md5",
            "sign": self._generate_sign(method, params, timestamp),
        }
        
        if self.access_token:
            request_params["access_token"] = self.access_token
        
        # 发送请求
        url = f"{self.base_url}/{method.replace('.', '/')}"
        response = await self._client.post(
            url,
            params=request_params,
            json=params,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 检查响应
        if result.get("err_no") != 0:
            raise Exception(f"抖音API错误: {result.get('message', '未知错误')}")
        
        return result.get("data", {})
    
    async def get_order_list(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        order_status: Optional[int] = None,
        page: int = 0,
        size: int = 100,
    ) -> Dict[str, Any]:
        """
        获取订单列表
        
        Args:
            start_time: 开始时间戳（秒）
            end_time: 结束时间戳（秒）
            order_status: 订单状态筛选
            page: 页码，从0开始
            size: 每页数量，最大100
        
        Returns:
            订单列表数据
        """
        params = {
            "page": page,
            "size": size,
        }
        
        if start_time and end_time:
            params["create_time_start"] = start_time
            params["create_time_end"] = end_time
        
        if order_status is not None:
            params["order_status"] = order_status
        
        return await self._request("order.searchList", params)
    
    async def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        """
        获取订单详情
        
        Args:
            order_id: 订单号
        
        Returns:
            订单详情数据
        """
        params = {
            "shop_order_id": order_id,
        }
        return await self._request("order.orderDetail", params)
    
    async def get_aftersale_list(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        aftersale_status: Optional[int] = None,
        page: int = 0,
        size: int = 100,
    ) -> Dict[str, Any]:
        """
        获取售后单列表
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            aftersale_status: 售后状态筛选
            page: 页码
            size: 每页数量
        
        Returns:
            售后单列表数据
        """
        params = {
            "page": page,
            "size": size,
        }
        
        if start_time and end_time:
            params["create_time_start"] = start_time
            params["create_time_end"] = end_time
        
        if aftersale_status is not None:
            params["aftersale_status"] = aftersale_status
        
        return await self._request("afterSale.List", params)
    
    async def get_aftersale_detail(self, aftersale_id: str) -> Dict[str, Any]:
        """
        获取售后单详情
        
        Args:
            aftersale_id: 售后单号
        
        Returns:
            售后单详情数据
        """
        params = {
            "aftersale_id": aftersale_id,
        }
        return await self._request("afterSale.Detail", params)
    
    async def get_logistics_track(self, order_id: str) -> Dict[str, Any]:
        """
        获取物流轨迹
        
        Args:
            order_id: 订单号
        
        Returns:
            物流轨迹数据
        """
        params = {
            "order_id": order_id,
        }
        return await self._request("logistics.trackNoRouteDetail", params)
    
    async def close(self):
        """关闭客户端连接"""
        await self._client.aclose()

