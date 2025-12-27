'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Table,
  Input,
  DatePicker,
  Button,
  Space,
  InputNumber,
  message,
  Tooltip,
  Tag,
  Modal,
  Alert,
  Progress,
  Upload,
  Image,
  Popover,
} from 'antd'
import type { UploadChangeParam } from 'antd/es/upload'
import {
  SearchOutlined,
  ReloadOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
  PlusOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue, SorterResult } from 'antd/es/table/interface'
import dayjs from 'dayjs'
import type { SkuStats } from '@/types'
import { statsApi, logisticsApi, skuApi } from '@/lib/api'

// 后端 API 基础地址
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8000'

const { RangePicker } = DatePicker

interface Props {
  compact?: boolean  // 紧凑模式（用于看板）
}

interface LogisticsTask {
  status: string
  total: number
  checked: number
  signed: number
  progress: string
  sku_stats_count?: number
  error?: string
}

export default function SkuStatsTable({ compact = false }: Props) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<SkuStats[]>([])
  const [total, setTotal] = useState(0)
  const [isRealtime, setIsRealtime] = useState(false)  // 是否实时计算
  const [lastCalculatedAt, setLastCalculatedAt] = useState<string>('')
  
  // 物流刷新状态
  const [logisticsLoading, setLogisticsLoading] = useState(false)
  const [logisticsTask, setLogisticsTask] = useState<LogisticsTask | null>(null)
  const logisticsPollingRef = useRef<NodeJS.Timeout | null>(null)
  
  // 图片上传状态
  const [uploadingSkuCode, setUploadingSkuCode] = useState<string | null>(null)
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  // 从 localStorage 读取图片时间戳
  const getImageTimestamps = (): Record<string, number> => {
    if (typeof window === 'undefined') return {}
    try {
      const stored = localStorage.getItem('sku_image_timestamps')
      return stored ? JSON.parse(stored) : {}
    } catch {
      return {}
    }
  }

  const [imageTimestamps, setImageTimestamps] = useState<Record<string, number>>(getImageTimestamps)
  
  // 筛选条件
  const [searchCode, setSearchCode] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [topN, setTopN] = useState<number | null>(compact ? 10 : null)
  
  // 分页
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: compact ? 10 : 20,
  })
  
  // 排序
  const [sortInfo, setSortInfo] = useState<{
    field: string
    order: 'asc' | 'desc'
  }>({
    field: 'pending_ship_count',
    order: 'desc',
  })

  // 获取数据
  const fetchData = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        sort_by: sortInfo.field,
        sort_order: sortInfo.order,
      }
      
      if (searchCode) {
        params.sku_code = searchCode
      }
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      if (topN) {
        params.top_n = topN
      }
      
      const response = await statsApi.getSkuStats(params) as unknown as {
        items: SkuStats[]
        total: number
        is_realtime: boolean
      }
      setData(response.items || [])
      setTotal(response.total || 0)
      setIsRealtime(response.is_realtime || false)

      // 从数据中获取最后计算时间
      if (response.items?.length > 0 && response.items[0].last_calculated_at) {
        setLastCalculatedAt(response.items[0].last_calculated_at)
      }

      // 刷新图片时间戳（从 localStorage 读取最新值）
      setImageTimestamps(getImageTimestamps())
    } catch (error) {
      console.error('获取SKU统计失败:', error)
      message.error('获取数据失败，请检查后端服务是否启动')
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [pagination, sortInfo])

  // 监听页面可见性变化和 localStorage 变化，确保图片时间戳同步
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        setImageTimestamps(getImageTimestamps())
      }
    }

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'sku_image_timestamps' && e.newValue) {
        try {
          setImageTimestamps(JSON.parse(e.newValue))
        } catch {
          // 解析失败，忽略
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('storage', handleStorageChange)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('storage', handleStorageChange)
    }
  }, [])

  // 处理搜索（重置页码到第一页）
  const handleSearch = () => {
    if (pagination.current === 1) {
      // 如果已经在第一页，直接获取数据
      fetchData()
    } else {
      // 重置到第一页，useEffect 会自动触发 fetchData
      setPagination(prev => ({ ...prev, current: 1 }))
    }
  }

  // 处理表格变化
  const handleTableChange = (
    newPagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<SkuStats> | SorterResult<SkuStats>[]
  ) => {
    setPagination({
      current: newPagination.current || 1,
      pageSize: newPagination.pageSize || 20,
    })
    
    if (!Array.isArray(sorter) && sorter.field) {
      setSortInfo({
        field: sorter.field as string,
        order: sorter.order === 'ascend' ? 'asc' : 'desc',
      })
    }
  }

  // 手动修改退货率
  const handleUpdateReturnRate = (record: SkuStats) => {
    let newRate = record.estimated_return_rate
    
    Modal.confirm({
      title: '修改退货率',
      icon: <EditOutlined />,
      content: (
        <div style={{ marginTop: 16 }}>
          <p>SKU: {record.sku_code}</p>
          <p style={{ marginTop: 8 }}>
            当前退货率: {(record.estimated_return_rate * 100).toFixed(1)}%
          </p>
          <InputNumber
            style={{ width: '100%', marginTop: 8 }}
            min={0}
            max={100}
            defaultValue={record.estimated_return_rate * 100}
            formatter={(value) => `${value}%`}
            parser={(value) => value?.replace('%', '') as unknown as number}
            onChange={(value) => {
              newRate = (value || 0) / 100
            }}
          />
        </div>
      ),
      onOk: async () => {
        try {
          await statsApi.updateReturnRate(record.sku_code, newRate)
          message.success('退货率更新成功')
          fetchData()
        } catch (error) {
          message.error('更新失败，请重试')
        }
      },
    })
  }

  // 刷新物流并重算统计
  const handleRefreshLogistics = async () => {
    Modal.confirm({
      title: '刷新物流签收状态',
      icon: <SyncOutlined />,
      content: (
        <div>
          <p>此操作将检查所有已发货订单的物流签收状态，并自动重新计算统计数据。</p>
          <p style={{ color: '#faad14', marginTop: 8 }}>
            注意：此操作可能需要较长时间（取决于订单数量），请耐心等待。
          </p>
        </div>
      ),
      okText: '开始刷新',
      cancelText: '取消',
      onOk: async () => {
        setLogisticsLoading(true)
        setLogisticsTask(null)
        try {
          // 默认不限制：由后端按批次把符合条件的订单全部处理（limit=0）
          const response = await logisticsApi.checkAll() as unknown as {
            task_id: string | null
            count: number
          }
          
          if (!response.task_id) {
            message.info('没有需要检查的订单')
            setLogisticsLoading(false)
            return
          }
          
          message.info(`开始检查 ${response.count} 个订单的物流状态...`)
          
          // 开始轮询任务状态
          startLogisticsPolling(response.task_id)
        } catch (error) {
          message.error('启动物流检查失败')
          setLogisticsLoading(false)
        }
      },
    })
  }
  
  // 轮询物流检查任务状态
  const startLogisticsPolling = (taskId: string) => {
    const poll = async () => {
      try {
        const status = await logisticsApi.getCheckStatus(taskId) as unknown as LogisticsTask
        setLogisticsTask(status)
        
        if (status.status === 'completed') {
          message.success(`物流检查完成！已签收 ${status.signed} 个订单，统计已更新`)
          setLogisticsLoading(false)
          if (logisticsPollingRef.current) {
            clearInterval(logisticsPollingRef.current)
          }
          fetchData()
        } else if (status.status === 'failed') {
          message.error(`物流检查失败: ${status.error}`)
          setLogisticsLoading(false)
          if (logisticsPollingRef.current) {
            clearInterval(logisticsPollingRef.current)
          }
        }
      } catch (error) {
        console.error('轮询任务状态失败:', error)
      }
    }
    
    poll()
    logisticsPollingRef.current = setInterval(poll, 2000)
  }
  
  // 组件卸载时清理轮询
  useEffect(() => {
    return () => {
      if (logisticsPollingRef.current) {
        clearInterval(logisticsPollingRef.current)
      }
    }
  }, [])
  
  // 处理图片上传
  const handleImageUpload = async (skuCode: string, file: File) => {
    setUploadingSkuCode(skuCode)
    try {
      await skuApi.uploadImage(skuCode, file)
      message.success('图片上传成功')
      // 更新该SKU的图片时间戳，强制刷新缓存
      const newTimestamps = {
        ...getImageTimestamps(),
        [skuCode]: Date.now()
      }
      // 保存到 localStorage
      localStorage.setItem('sku_image_timestamps', JSON.stringify(newTimestamps))
      setImageTimestamps(newTimestamps)
      fetchData() // 刷新数据
    } catch (error) {
      console.error('图片上传失败:', error)
      message.error('图片上传失败')
    } finally {
      setUploadingSkuCode(null)
    }
  }
  
  // 图片预览
  const handlePreview = (imageUrl: string, skuCode: string) => {
    const timestamp = imageTimestamps[skuCode]
    setPreviewImage(`${API_BASE_URL}${imageUrl}${timestamp ? `?t=${timestamp}` : ''}`)
    setPreviewOpen(true)
  }

  // 表格列定义
  const columns: ColumnsType<SkuStats> = [
    {
      title: '商品图片',
      dataIndex: 'image_url',
      key: 'image_url',
      fixed: 'left',
      width: 80,
      render: (imageUrl: string | null, record) => {
        const isUploading = uploadingSkuCode === record.sku_code
        
        if (imageUrl) {
          // 有图片，显示缩略图
          const timestamp = imageTimestamps[record.sku_code]
          const fullImageUrl = `${API_BASE_URL}${imageUrl}${timestamp ? `?t=${timestamp}` : ''}`

          return (
            <Popover
              content={
                <img
                  src={fullImageUrl}
                  alt={record.sku_name || record.sku_code}
                  style={{ display: 'block' }}
                />
              }
              trigger="hover"
              placement="rightTop"
              mouseEnterDelay={0.5}
              overlayClassName="image-preview-popover"
              arrow={false}
            >
              <div style={{ position: 'relative', cursor: 'pointer' }}>
                <Image
                  src={fullImageUrl}
                  alt={record.sku_name || record.sku_code}
                  width={50}
                  height={50}
                  style={{ objectFit: 'cover', borderRadius: 4 }}
                  preview={false}
                  onClick={() => handlePreview(imageUrl, record.sku_code)}
                />
                <Upload
                  accept="image/*"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    handleImageUpload(record.sku_code, file)
                    return false
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      background: 'rgba(0,0,0,0.5)',
                      opacity: 0,
                      transition: 'opacity 0.3s',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: 4,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
                    onMouseMove={(e) => e.stopPropagation()}
                  >
                    <PlusOutlined style={{ color: '#fff', fontSize: 16 }} />
                  </div>
                </Upload>
              </div>
            </Popover>
          )
        }
        
        // 无图片，显示上传按钮
        return (
          <Upload
            accept="image/*"
            showUploadList={false}
            beforeUpload={(file) => {
              handleImageUpload(record.sku_code, file)
              return false
            }}
          >
            <div
              style={{
                width: 50,
                height: 50,
                border: '1px dashed #d9d9d9',
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                background: '#fafafa',
              }}
            >
              {isUploading ? <LoadingOutlined /> : <PlusOutlined style={{ color: '#8a8a8a' }} />}
            </div>
          </Upload>
        )
      },
    },
    {
      title: 'SKU编码',
      dataIndex: 'sku_code',
      key: 'sku_code',
      fixed: 'left',
      width: 140,
      render: (code: string, record) => (
        <Tooltip title={record.sku_name}>
          <span style={{ fontFamily: 'monospace' }}>{code}</span>
        </Tooltip>
      ),
    },
    {
      title: '待发货量',
      dataIndex: 'pending_ship_count',
      key: 'pending_ship_count',
      width: 100,
      sorter: true,
      render: (count: number) => (
        <span style={{ color: '#fe2c55', fontWeight: 600 }}>{count}</span>
      ),
    },
    {
      title: '售后未完结',
      dataIndex: 'aftersale_pending_count',
      key: 'aftersale_pending_count',
      width: 100,
      sorter: true,
      render: (count: number) => (
        <span style={{ color: '#faad14' }}>{count}</span>
      ),
    },
    {
      title: '已签收数量',
      dataIndex: 'signed_count',
      key: 'signed_count',
      width: 100,
      sorter: true,
      render: (count: number) => (
        <span style={{ color: '#52c41a' }}>{count}</span>
      ),
    },
    {
      title: '已签收退货',
      dataIndex: 'signed_return_count',
      key: 'signed_return_count',
      width: 100,
      sorter: true,
    },
    {
      title: '预估退货率',
      dataIndex: 'estimated_return_rate',
      key: 'estimated_return_rate',
      width: 120,
      sorter: true,
      render: (rate: number, record) => (
        <Space>
          <span>{(rate * 100).toFixed(1)}%</span>
          {record.is_rate_manual && (
            <Tag color="blue" style={{ fontSize: 10 }}>手动</Tag>
          )}
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleUpdateReturnRate(record)}
            style={{ padding: 0 }}
          />
        </Space>
      ),
    },
    {
      title: '在途未签收',
      dataIndex: 'in_transit_count',
      key: 'in_transit_count',
      width: 100,
      sorter: true,
    },
    {
      title: '在途预估退货',
      dataIndex: 'in_transit_return_estimate',
      key: 'in_transit_return_estimate',
      width: 110,
      sorter: true,
    },
    {
      title: '品质退货数',
      dataIndex: 'quality_return_count',
      key: 'quality_return_count',
      width: 100,
      sorter: true,
      render: (count: number) => (
        <span style={{ color: count > 0 ? '#ff4d4f' : undefined }}>{count || 0}</span>
      ),
    },
    {
      title: '品质退货率',
      dataIndex: 'quality_return_rate',
      key: 'quality_return_rate',
      width: 100,
      sorter: true,
      render: (rate: number) => {
        const percent = ((rate || 0) * 100).toFixed(1)
        let color = '#52c41a'
        if (rate > 0.2) color = '#ff4d4f'
        else if (rate > 0.1) color = '#faad14'
        
        return <span style={{ color }}>{percent}%</span>
      },
    },
    {
      title: '预估商品缺口',
      dataIndex: 'stock_gap',
      key: 'stock_gap',
      width: 120,
      sorter: true,
      render: (gap: number) => {
        let color = '#52c41a'
        if (gap > 100) color = '#ff4d4f'
        else if (gap > 50) color = '#faad14'
        
        return (
          <Space>
            <span style={{ color, fontWeight: 600 }}>{gap}</span>
            {gap > 100 && (
              <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
            )}
          </Space>
        )
      },
    },
  ]

  // 紧凑模式下减少列
  const compactColumns = columns.filter((col) =>
    ['image_url', 'sku_code', 'pending_ship_count', 'aftersale_pending_count', 'signed_count', 'stock_gap'].includes(
      col.key as string
    )
  )

  return (
    <div>
      {!compact && (
        <>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input
              placeholder="搜索SKU编码"
              prefix={<SearchOutlined />}
              value={searchCode}
              onChange={(e) => setSearchCode(e.target.value)}
              onPressEnter={handleSearch}
              style={{ width: 200 }}
            />
            <RangePicker
              value={dateRange}
              onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
              placeholder={['订单开始日期', '订单结束日期']}
            />
            <InputNumber
              placeholder="Top N"
              min={1}
              max={100}
              value={topN}
              onChange={(value) => setTopN(value)}
              style={{ width: 100 }}
            />
            <Button type="primary" onClick={handleSearch}>
              查询
            </Button>
            <Button 
              icon={<SyncOutlined spin={logisticsLoading} />} 
              onClick={handleRefreshLogistics}
              loading={logisticsLoading}
            >
              刷新物流并重算
            </Button>
          </Space>
          
          {/* 物流刷新进度 */}
          {logisticsTask && logisticsTask.status === 'processing' && (
            <Alert
              type="info"
              showIcon
              icon={<SyncOutlined spin />}
              message={logisticsTask.progress}
              description={
                <div>
                  <Progress 
                    percent={Math.round((logisticsTask.checked / logisticsTask.total) * 100)} 
                    size="small"
                    status="active"
                  />
                  <span style={{ fontSize: 12, color: '#8a8a8a' }}>
                    已检查 {logisticsTask.checked}/{logisticsTask.total}，
                    已签收 {logisticsTask.signed} 个
                  </span>
                </div>
              }
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      )}
      
      {/* 状态提示 */}
      {!compact && (
        <div style={{ marginBottom: 8, color: '#8a8a8a', fontSize: 12 }}>
          {isRealtime ? (
            <Tag color="blue">实时计算</Tag>
          ) : (
            lastCalculatedAt && (
              <span>最后计算时间: {dayjs(lastCalculatedAt).format('YYYY-MM-DD HH:mm:ss')}</span>
            )
          )}
          {data.length === 0 && !loading && (
            <span style={{ marginLeft: 8, color: '#faad14' }}>
              暂无数据，请先导入订单和售后数据
            </span>
          )}
        </div>
      )}
      
      <Table
        columns={compact ? compactColumns : columns}
        dataSource={data}
        rowKey="sku_code"
        loading={loading}
        pagination={compact ? false : {
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
        onChange={handleTableChange}
        scroll={{ x: compact ? undefined : 1300 }}
        size={compact ? 'small' : 'middle'}
      />
      
      {/* 图片预览 Modal */}
      <Modal
        open={previewOpen}
        title="商品图片预览"
        footer={null}
        onCancel={() => setPreviewOpen(false)}
      >
        {previewImage && (
          <img
            alt="商品图片"
            style={{ width: '100%' }}
            src={previewImage}
          />
        )}
      </Modal>
    </div>
  )
}

