import axios from 'axios'

// API 基础地址
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10分钟超时，大文件导入需要时间
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token 等认证信息
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// SKU 统计相关 API
export const statsApi = {
  // 获取 SKU 统计列表
  getSkuStats: (params?: {
    start_date?: string
    end_date?: string
    sku_code?: string
    top_n?: number
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  }) => api.get('/stats/sku', { params }),

  // 重新计算统计
  calculateStats: () => api.post('/stats/sku/calculate'),

  // 更新退货率
  updateReturnRate: (skuCode: string, returnRate: number) =>
    api.put(`/stats/sku/${skuCode}/return-rate`, null, {
      params: { return_rate: returnRate },
    }),

  // 获取省份统计
  getProvinceStats: (params?: {
    start_date?: string
    end_date?: string
    sku_code?: string
  }) => api.get('/stats/province', { params }),

  // 获取统计汇总（数据看板用）
  getSummary: () => api.get('/stats/summary'),

  // 获取订单趋势数据
  getOrderTrend: (params?: {
    granularity?: 'day' | 'hour' | 'minute'
    start_date?: string
    end_date?: string
    days?: number
  }) => api.get('/stats/orders/trend', { params }),

  // 获取省份SKU退货率矩阵
  getProvinceSkuStats: (params?: {
    start_date?: string
    end_date?: string
    province_name?: string
    sku_code?: string
    limit?: number
  }) => api.get('/stats/province-sku', { params }),
}

// 订单相关 API
export const ordersApi = {
  // 获取订单列表
  getOrders: (params?: {
    page?: number
    page_size?: number
    order_status?: number
    province_id?: string
    start_date?: string
    end_date?: string
  }) => api.get('/orders', { params }),

  // 获取订单详情
  getOrderDetail: (orderId: string) => api.get(`/orders/${orderId}`),
}

// 文件上传相关 API
export const uploadApi = {
  // 上传订单文件
  uploadOrders: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/orders', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 上传售后单文件
  uploadAftersales: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/aftersales', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 上传全部并计算统计
  uploadAll: (ordersFile: File, aftersalesFile: File) => {
    const formData = new FormData()
    formData.append('orders_file', ordersFile)
    formData.append('aftersales_file', aftersalesFile)
    return api.post('/upload/all', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 查询导入任务状态
  getTaskStatus: (taskId: string) => api.get(`/upload/status/${taskId}`),

  // 列出所有任务
  listTasks: () => api.get('/upload/tasks'),
}

// 物流查询相关 API
export const logisticsApi = {
  // 查询单个物流
  query: (trackingNumber: string, companyName: string) =>
    api.get(`/logistics/query/${trackingNumber}`, {
      params: { company_name: companyName },
    }),

  // 批量检查物流状态
  checkAll: (limit?: number) =>
    api.post('/logistics/check-all', null, {
      params: { limit },
    }),

  // 查询物流检查任务状态
  getCheckStatus: (taskId: string) => api.get(`/logistics/check-status/${taskId}`),

  // 获取物流统计
  getStats: () => api.get('/logistics/stats'),
}

// 系统配置相关 API
export const configApi = {
  // 获取所有配置
  getAll: () => api.get('/config'),

  // 获取单个配置
  get: (key: string) => api.get(`/config/${key}`),

  // 更新配置
  update: (key: string, value: string) =>
    api.put(`/config/${key}`, { config_value: value }),

  // 批量更新配置
  batchUpdate: (configs: Array<{ config_key: string; config_value: string; description: string }>) =>
    api.post('/config/batch', configs),
}

// SKU 图片上传
export const skuApi = {
  // 上传 SKU 图片
  uploadImage: (skuCode: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/upload/sku-image/${encodeURIComponent(skuCode)}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export default api

