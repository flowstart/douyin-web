'use client'

import { useState, useEffect } from 'react'
import { Card, Spin, Radio, Space, DatePicker, message } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { statsApi } from '@/lib/api'
import dynamic from 'next/dynamic'

// 动态导入图表组件，避免 SSR 问题
const Line = dynamic(
  () => import('@ant-design/charts').then((mod) => mod.Line),
  { ssr: false, loading: () => <Spin /> }
)

const { RangePicker } = DatePicker

interface TrendItem {
  time_label: string
  order_count: number
  pending_ship_count: number
  shipped_count: number
  refunded_count: number
}

interface Props {
  compact?: boolean
}

export default function OrderTrendChart({ compact = false }: Props) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<TrendItem[]>([])
  const [granularity, setGranularity] = useState<'day' | 'hour'>('day')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

  const fetchData = async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = {
        granularity,
        days: granularity === 'day' ? 7 : 1,
      }
      
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      
      const response = await statsApi.getOrderTrend(params) as TrendItem[]
      setData(response || [])
    } catch (error) {
      console.error('获取订单趋势失败:', error)
      message.error('获取订单趋势数据失败')
      setData([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [granularity, dateRange])

  // 转换数据格式为图表需要的格式
  const chartData = data.flatMap((item) => [
    { time: item.time_label, count: item.order_count, type: '订单总数' },
    { time: item.time_label, count: item.pending_ship_count, type: '待发货' },
    { time: item.time_label, count: item.shipped_count, type: '已发货' },
  ])

  const config = {
    data: chartData,
    xField: 'time',
    yField: 'count',
    seriesField: 'type',
    smooth: true,
    animation: {
      appear: {
        animation: 'path-in',
        duration: 1000,
      },
    },
    color: ['#fe2c55', '#52c41a', '#1890ff'],
    legend: {
      position: 'top-right' as const,
    },
    xAxis: {
      label: {
        autoRotate: true,
        formatter: (text: string) => {
          // 简化日期显示
          if (granularity === 'day') {
            return text.slice(5) // 只显示月-日
          }
          return text.slice(11, 16) // 只显示时:分
        },
      },
    },
    yAxis: {
      label: {
        formatter: (value: string) => {
          const num = parseInt(value)
          if (num >= 10000) return `${(num / 10000).toFixed(1)}w`
          if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
          return value
        },
      },
    },
    tooltip: {
      shared: true,
    },
  }

  return (
    <Card
      title={
        <Space>
          <LineChartOutlined />
          <span>订单趋势</span>
        </Space>
      }
      extra={
        !compact && (
          <Space>
            <Radio.Group
              value={granularity}
              onChange={(e) => setGranularity(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              size="small"
            >
              <Radio.Button value="day">按天</Radio.Button>
              <Radio.Button value="hour">按小时</Radio.Button>
            </Radio.Group>
            <RangePicker
              size="small"
              value={dateRange}
              onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
            />
          </Space>
        )
      }
      style={{ marginBottom: 24 }}
    >
      <Spin spinning={loading}>
        <div style={{ height: compact ? 200 : 300 }}>
          {data.length > 0 ? (
            <Line {...config} />
          ) : (
            <div
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#8a8a8a',
              }}
            >
              暂无数据
            </div>
          )}
        </div>
      </Spin>
    </Card>
  )
}

