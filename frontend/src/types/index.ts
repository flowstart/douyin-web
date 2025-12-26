// SKU 统计数据
export interface SkuStats {
  sku_id: string
  sku_code: string
  sku_name: string | null
  product_name: string | null
  image_url: string | null        // 商品图片URL
  pending_ship_count: number      // 待发货量
  aftersale_pending_count: number // 售后未完结数量
  signed_count: number            // 已签收数量
  signed_return_count: number     // 已签收订单的退货数量
  estimated_return_rate: number   // 预估退货率
  is_rate_manual: boolean         // 是否手动修改
  in_transit_count: number        // 已发货在途未签收数量
  in_transit_return_estimate: number // 已发货在途预估退货数量
  stock_gap: number               // 预估商品缺口
  quality_return_count: number    // 品质问题退货数量
  quality_return_rate: number     // 品质退货率
  last_calculated_at: string | null  // 最后计算时间
}

// SKU 统计列表响应
export interface SkuStatsListResponse {
  total: number
  items: SkuStats[]
  is_realtime: boolean  // 是否实时计算
}

// 订单 SKU
export interface OrderSku {
  sku_id: string
  sku_code: string | null
  sku_name: string | null
  product_id: string | null
  product_name: string | null
  quantity: number
  price: number
}

// 订单
export interface Order {
  order_id: string
  order_status: number
  order_status_desc: string
  create_time: string
  update_time: string | null
  pay_time: string | null
  receiver_name: string | null
  province_id: string | null
  province_name: string | null
  city_name: string | null
  logistics_code: string | null
  logistics_status: number | null
  logistics_status_desc: string | null
  is_signed: boolean
  sign_time: string | null
  total_amount: number
  pay_amount: number
  sku_list: OrderSku[]
}

// 订单列表响应
export interface OrderListResponse {
  total: number
  items: Order[]
}

// 省份统计
export interface ProvinceStats {
  province_name: string
  order_count: number
  return_count: number
  return_rate: number
}

// 同步结果
export interface SyncResult {
  message: string
  stats: {
    total: number
    created: number
    updated: number
  }
  time_range: {
    start: string
    end: string
  }
}

// 查询参数
export interface SkuStatsQuery {
  start_date?: string
  end_date?: string
  sku_code?: string
  top_n?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

