'use client'

import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Input,
  Space,
  Spin,
  message,
  Tabs,
  Tag,
  DatePicker,
  Button,
} from 'antd'
import { SearchOutlined, EnvironmentOutlined, LineChartOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { statsApi } from '@/lib/api'

const { RangePicker } = DatePicker

interface ProvinceSkuItem {
  province_name: string
  sku_code: string
  sku_name: string | null
  order_count: number
  return_count: number
  return_rate: number
}

interface ProvinceItem {
  province_name: string
  order_count: number
  return_count: number
  return_rate: number
}

export default function ProvinceAnalysis() {
  const [loading, setLoading] = useState(false)
  const [provinceData, setProvinceData] = useState<ProvinceItem[]>([])
  const [provinceSkuData, setProvinceSkuData] = useState<ProvinceSkuItem[]>([])
  const [searchSku, setSearchSku] = useState('')
  const [searchProvince, setSearchProvince] = useState('')
  const [activeTab, setActiveTab] = useState('province')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

  // 加载省份统计
  const loadProvinceStats = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      
      const response = await statsApi.getProvinceStats(params) as unknown as { items: ProvinceItem[] }
      setProvinceData(response.items || [])
    } catch (error) {
      console.error('加载省份统计失败:', error)
      message.error('加载省份统计失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载省份 x SKU 退货率矩阵
  const loadProvinceSkuStats = async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: 200 }
      if (searchSku) params.sku_code = searchSku
      if (searchProvince) params.province_name = searchProvince
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      
      const response = await statsApi.getProvinceSkuStats(params) as unknown as { items: ProvinceSkuItem[] }
      setProvinceSkuData(response.items || [])
    } catch (error) {
      console.error('加载省份SKU统计失败:', error)
      message.error('加载省份SKU统计失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理查询
  const handleSearch = () => {
    if (activeTab === 'province') {
      loadProvinceStats()
    } else {
      loadProvinceSkuStats()
    }
  }

  useEffect(() => {
    if (activeTab === 'province') {
      loadProvinceStats()
    } else {
      loadProvinceSkuStats()
    }
  }, [activeTab])

  // 省份汇总表格列
  const provinceColumns: ColumnsType<ProvinceItem> = [
    {
      title: '省份',
      dataIndex: 'province_name',
      key: 'province_name',
      width: 120,
      render: (name: string) => (
        <Space>
          <EnvironmentOutlined style={{ color: '#1890ff' }} />
          <span>{name}</span>
        </Space>
      ),
    },
    {
      title: '订单数',
      dataIndex: 'order_count',
      key: 'order_count',
      width: 100,
      sorter: (a, b) => a.order_count - b.order_count,
    },
    {
      title: '退货数',
      dataIndex: 'return_count',
      key: 'return_count',
      width: 100,
      sorter: (a, b) => a.return_count - b.return_count,
      render: (count: number) => (
        <span style={{ color: count > 0 ? '#ff4d4f' : undefined }}>{count}</span>
      ),
    },
    {
      title: '退货率',
      dataIndex: 'return_rate',
      key: 'return_rate',
      width: 100,
      sorter: (a, b) => a.return_rate - b.return_rate,
      defaultSortOrder: 'descend',
      render: (rate: number) => {
        let color = '#52c41a'
        if (rate > 0.2) color = '#ff4d4f'
        else if (rate > 0.1) color = '#faad14'
        
        return (
          <Tag color={rate > 0.2 ? 'red' : rate > 0.1 ? 'orange' : 'green'}>
            {(rate * 100).toFixed(1)}%
          </Tag>
        )
      },
    },
  ]

  // 省份 x SKU 表格列
  const provinceSkuColumns: ColumnsType<ProvinceSkuItem> = [
    {
      title: '省份',
      dataIndex: 'province_name',
      key: 'province_name',
      width: 100,
      filters: [...new Set(provinceSkuData.map(d => d.province_name))].map(p => ({
        text: p,
        value: p,
      })),
      onFilter: (value, record) => record.province_name === value,
    },
    {
      title: 'SKU编码',
      dataIndex: 'sku_code',
      key: 'sku_code',
      width: 140,
      render: (code: string, record) => (
        <span style={{ fontFamily: 'monospace' }} title={record.sku_name || ''}>
          {code}
        </span>
      ),
    },
    {
      title: 'SKU名称',
      dataIndex: 'sku_name',
      key: 'sku_name',
      ellipsis: true,
    },
    {
      title: '订单数',
      dataIndex: 'order_count',
      key: 'order_count',
      width: 80,
      sorter: (a, b) => a.order_count - b.order_count,
    },
    {
      title: '退货数',
      dataIndex: 'return_count',
      key: 'return_count',
      width: 80,
      sorter: (a, b) => a.return_count - b.return_count,
    },
    {
      title: '退货率',
      dataIndex: 'return_rate',
      key: 'return_rate',
      width: 100,
      sorter: (a, b) => a.return_rate - b.return_rate,
      defaultSortOrder: 'descend',
      render: (rate: number) => {
        let color = '#52c41a'
        if (rate > 0.3) color = '#ff4d4f'
        else if (rate > 0.15) color = '#faad14'
        
        return <span style={{ color, fontWeight: 600 }}>{(rate * 100).toFixed(1)}%</span>
      },
    },
  ]

  const tabItems = [
    {
      key: 'province',
      label: (
        <Space>
          <EnvironmentOutlined />
          省份汇总
        </Space>
      ),
      children: (
        <Spin spinning={loading}>
          <Table
            columns={provinceColumns}
            dataSource={provinceData}
            rowKey="province_name"
            pagination={{ pageSize: 20, showSizeChanger: true }}
            size="middle"
          />
        </Spin>
      ),
    },
    {
      key: 'province-sku',
      label: (
        <Space>
          <LineChartOutlined />
          省份 × SKU 分析
        </Space>
      ),
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="搜索省份"
              prefix={<SearchOutlined />}
              value={searchProvince}
              onChange={(e) => setSearchProvince(e.target.value)}
              style={{ width: 150 }}
            />
            <Input
              placeholder="搜索SKU"
              prefix={<SearchOutlined />}
              value={searchSku}
              onChange={(e) => setSearchSku(e.target.value)}
              style={{ width: 200 }}
            />
            <button
              onClick={loadProvinceSkuStats}
              className="ant-btn ant-btn-primary"
            >
              查询
            </button>
          </Space>
          
          <Spin spinning={loading}>
            <Table
              columns={provinceSkuColumns}
              dataSource={provinceSkuData}
              rowKey={(record) => `${record.province_name}-${record.sku_code}`}
              pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
              size="middle"
              scroll={{ x: 800 }}
            />
          </Spin>
        </div>
      ),
    },
  ]

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
          placeholder={['订单开始日期', '订单结束日期']}
        />
        <Button type="primary" onClick={handleSearch}>
          查询
        </Button>
      </Space>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
      />
    </Card>
  )
}

