'use client'

import { useState, useEffect } from 'react'
import {
  Table,
  Input,
  Select,
  DatePicker,
  Button,
  Space,
  Tag,
  Card,
  message,
  Tooltip,
  Modal,
  Descriptions,
  Empty,
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  EyeOutlined,
  CarOutlined,
} from '@ant-design/icons'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue, SorterResult } from 'antd/es/table/interface'
import dayjs from 'dayjs'
import type { Order } from '@/types'
import { ordersApi, logisticsApi } from '@/lib/api'

const { RangePicker } = DatePicker
const { Option } = Select

// 订单状态映射
const ORDER_STATUS_MAP: Record<number, { text: string; color: string }> = {
  1: { text: '待支付', color: 'default' },
  2: { text: '待发货', color: 'orange' },
  3: { text: '已发货', color: 'blue' },
  4: { text: '已签收', color: 'green' },
  5: { text: '已取消', color: 'red' },
  6: { text: '售后中', color: 'purple' },
}

interface OrderListResponse {
  items: Order[]
  total: number
}

export default function OrderList() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  
  // 筛选条件
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<number | null>(null)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  
  // 分页
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
  })
  
  // 详情弹窗
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  
  // 物流弹窗
  const [logisticsVisible, setLogisticsVisible] = useState(false)
  const [logisticsLoading, setLogisticsLoading] = useState(false)
  const [logisticsData, setLogisticsData] = useState<{
    tracking_number: string
    company_name: string
    parsed_status: {
      state: string
      status_desc: string
      is_signed: boolean
      latest_info: string
      latest_time: string
    }
  } | null>(null)

  // 获取数据
  const fetchData = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
      }
      
      if (statusFilter !== null) {
        params.order_status = statusFilter
      }
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      
      const response = await ordersApi.getOrders(params) as unknown as OrderListResponse
      setData(response.items || [])
      setTotal(response.total || 0)
    } catch (error) {
      console.error('获取订单列表失败:', error)
      message.error('获取订单列表失败，请检查后端服务是否启动')
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [pagination])

  // 处理表格变化
  const handleTableChange = (
    newPagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    _sorter: SorterResult<Order> | SorterResult<Order>[]
  ) => {
    setPagination({
      current: newPagination.current || 1,
      pageSize: newPagination.pageSize || 20,
    })
  }

  // 查看订单详情
  const handleViewDetail = (record: Order) => {
    setSelectedOrder(record)
    setDetailVisible(true)
  }

  // 查看物流
  const handleViewLogistics = async (record: Order) => {
    if (!record.logistics_code) {
      message.warning('该订单没有物流单号')
      return
    }
    
    setSelectedOrder(record)
    setLogisticsVisible(true)
    setLogisticsLoading(true)
    setLogisticsData(null)
    
    try {
      const response = await logisticsApi.query(
        record.logistics_code,
        record.logistics_status_desc || '申通快递'
      )
      setLogisticsData(response as unknown as typeof logisticsData)
    } catch (error) {
      console.error('查询物流失败:', error)
      message.error('查询物流失败')
    } finally {
      setLogisticsLoading(false)
    }
  }

  // 本地搜索过滤
  const filteredData = data.filter((item) => {
    if (!searchText) return true
    const search = searchText.toLowerCase()
    return (
      item.order_id.toLowerCase().includes(search) ||
      item.receiver_name?.toLowerCase().includes(search) ||
      item.logistics_code?.toLowerCase().includes(search)
    )
  })

  // 表格列定义
  const columns: ColumnsType<Order> = [
    {
      title: '订单号',
      dataIndex: 'order_id',
      key: 'order_id',
      width: 180,
      fixed: 'left',
      render: (id: string) => (
        <Tooltip title={id}>
          <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
            {id.slice(0, 8)}...{id.slice(-4)}
          </span>
        </Tooltip>
      ),
    },
    {
      title: '订单状态',
      dataIndex: 'order_status',
      key: 'order_status',
      width: 100,
      render: (status: number) => {
        const config = ORDER_STATUS_MAP[status] || { text: '未知', color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '收件人',
      dataIndex: 'receiver_name',
      key: 'receiver_name',
      width: 100,
      render: (name: string) => name || '-',
    },
    {
      title: '收货地区',
      key: 'region',
      width: 120,
      render: (_, record) => (
        <span>{record.province_name || '-'}</span>
      ),
    },
    {
      title: '支付金额',
      dataIndex: 'pay_amount',
      key: 'pay_amount',
      width: 100,
      render: (amount: number) => (
        <span style={{ color: '#fe2c55' }}>¥{amount.toFixed(2)}</span>
      ),
    },
    {
      title: '支付时间',
      dataIndex: 'pay_time',
      key: 'pay_time',
      width: 160,
      render: (time: string) => time ? dayjs(time).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '物流状态',
      key: 'logistics',
      width: 120,
      render: (_, record) => {
        if (!record.logistics_code) {
          return <Tag color="default">无物流</Tag>
        }
        if (record.is_signed) {
          return <Tag color="green">已签收</Tag>
        }
        return <Tag color="blue">运输中</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      fixed: 'right',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
          {record.logistics_code && (
            <Button
              type="link"
              size="small"
              icon={<CarOutlined />}
              onClick={() => handleViewLogistics(record)}
            >
              物流
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索订单号/收件人/物流单号"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 260 }}
          />
          <Select
            placeholder="订单状态"
            allowClear
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
            style={{ width: 120 }}
          >
            {Object.entries(ORDER_STATUS_MAP).map(([key, config]) => (
              <Option key={key} value={Number(key)}>
                {config.text}
              </Option>
            ))}
          </Select>
          <RangePicker
            value={dateRange}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
            placeholder={['支付开始日期', '支付结束日期']}
          />
          <Button type="primary" onClick={fetchData}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => {
            setSearchText('')
            setStatusFilter(null)
            setDateRange(null)
            setPagination({ current: 1, pageSize: 20 })
          }}>
            重置
          </Button>
        </Space>
        
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="order_id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={handleTableChange}
          scroll={{ x: 1200 }}
          size="middle"
        />
      </Card>
      
      {/* 订单详情弹窗 */}
      <Modal
        title="订单详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={600}
      >
        {selectedOrder && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="订单号" span={2}>
              {selectedOrder.order_id}
            </Descriptions.Item>
            <Descriptions.Item label="订单状态">
              <Tag color={ORDER_STATUS_MAP[selectedOrder.order_status]?.color}>
                {ORDER_STATUS_MAP[selectedOrder.order_status]?.text || '未知'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="支付金额">
              <span style={{ color: '#fe2c55' }}>¥{selectedOrder.pay_amount.toFixed(2)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="收件人">
              {selectedOrder.receiver_name || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="收货地区">
              {selectedOrder.province_name} {selectedOrder.city_name}
            </Descriptions.Item>
            <Descriptions.Item label="下单时间">
              {selectedOrder.create_time ? dayjs(selectedOrder.create_time).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="支付时间">
              {selectedOrder.pay_time ? dayjs(selectedOrder.pay_time).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="物流单号" span={2}>
              {selectedOrder.logistics_code || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="物流状态">
              {selectedOrder.is_signed ? (
                <Tag color="green">已签收</Tag>
              ) : selectedOrder.logistics_code ? (
                <Tag color="blue">运输中</Tag>
              ) : (
                <Tag color="default">无物流</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="签收时间">
              {selectedOrder.sign_time ? dayjs(selectedOrder.sign_time).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
      
      {/* 物流查询弹窗 */}
      <Modal
        title="物流信息"
        open={logisticsVisible}
        onCancel={() => setLogisticsVisible(false)}
        footer={null}
        width={500}
      >
        {logisticsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <span>查询中...</span>
          </div>
        ) : logisticsData ? (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="物流单号">
              {logisticsData.tracking_number}
            </Descriptions.Item>
            <Descriptions.Item label="快递公司">
              {logisticsData.company_name}
            </Descriptions.Item>
            <Descriptions.Item label="物流状态">
              {logisticsData.parsed_status.is_signed ? (
                <Tag color="green">已签收</Tag>
              ) : (
                <Tag color="blue">{logisticsData.parsed_status.status_desc}</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="最新动态">
              {logisticsData.parsed_status.latest_info || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {logisticsData.parsed_status.latest_time || '-'}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="暂无物流信息" />
        )}
      </Modal>
    </div>
  )
}

