'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Upload,
  Button,
  Card,
  Steps,
  message,
  Space,
  Divider,
  Alert,
  Statistic,
  Row,
  Col,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import {
  UploadOutlined,
  FileExcelOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloudUploadOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'
import { uploadApi, logisticsApi, statsApi } from '@/lib/api'

interface UploadStats {
  total: number
  created: number
  updated: number
  skipped: number
}

interface LogisticsStats {
  total_orders: number
  with_logistics: number
  checked: number
  signed: number
  pending_check: number
}

interface TaskRecord {
  id: number
  task_id: string
  task_type: string
  status: 'processing' | 'completed' | 'failed'
  progress?: string
  filename?: string
  order_stats?: UploadStats
  aftersale_stats?: UploadStats
  sku_stats_count?: number
  error?: string
  started_at: string
  completed_at?: string
}

export default function DataUpload() {
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [ordersFile, setOrdersFile] = useState<UploadFile | null>(null)
  const [aftersalesFile, setAftersalesFile] = useState<UploadFile | null>(null)
  const [orderStats, setOrderStats] = useState<UploadStats | null>(null)
  const [aftersaleStats, setAftersaleStats] = useState<UploadStats | null>(null)
  const [logisticsStats, setLogisticsStats] = useState<LogisticsStats | null>(null)
  const [skuStatsCount, setSkuStatsCount] = useState<number>(0)
  const [taskProgress, setTaskProgress] = useState<string>('')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskList, setTaskList] = useState<TaskRecord[]>([])
  const [taskListLoading, setTaskListLoading] = useState(false)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  // 获取任务列表
  const fetchTaskList = useCallback(async () => {
    try {
      setTaskListLoading(true)
      const result = await uploadApi.listTasks() as unknown as { tasks: TaskRecord[]; count: number }
      setTaskList(result.tasks || [])
    } catch (error) {
      console.error('获取任务列表失败:', error)
    } finally {
      setTaskListLoading(false)
    }
  }, [])

  // 页面加载时获取任务列表
  useEffect(() => {
    fetchTaskList()
  }, [fetchTaskList])

  // 有任务在处理中时，定期刷新任务列表
  useEffect(() => {
    const hasProcessing = taskList.some(t => t.status === 'processing')
    if (hasProcessing) {
      const interval = setInterval(fetchTaskList, 3000)
      return () => clearInterval(interval)
    }
  }, [taskList, fetchTaskList])

  // 轮询任务状态
  const pollTaskStatus = useCallback(async (id: string) => {
    try {
      const status = await uploadApi.getTaskStatus(id) as unknown as TaskRecord
      setTaskProgress(status.progress || status.status)

      if (status.status === 'completed') {
        // 任务完成
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
        
        if (status.order_stats) setOrderStats(status.order_stats)
        if (status.aftersale_stats) setAftersaleStats(status.aftersale_stats)
        if (status.sku_stats_count) setSkuStatsCount(status.sku_stats_count)
        
        message.success('数据导入完成!')
        setCurrentStep(4)
        setLoading(false)
        setTaskId(null)
        setTaskProgress('')
        fetchTaskList() // 刷新任务列表
      } else if (status.status === 'failed') {
        // 任务失败
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
        message.error(`导入失败: ${status.error}`)
        setLoading(false)
        setTaskId(null)
        setTaskProgress('')
        fetchTaskList() // 刷新任务列表
      }
    } catch (error: unknown) {
      console.error('轮询状态失败:', error)
      // 如果是 404 错误（任务不存在），停止轮询
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { status?: number } }
        if (axiosError.response?.status === 404) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current)
            pollingRef.current = null
          }
          setLoading(false)
          setTaskId(null)
          setTaskProgress('')
          fetchTaskList()
        }
      }
    }
  }, [fetchTaskList])

  // 开始轮询
  const startPolling = (id: string) => {
    setTaskId(id)
    setTaskProgress('正在处理...')
    
    // 立即查询一次
    pollTaskStatus(id)
    
    // 每2秒轮询一次
    pollingRef.current = setInterval(() => {
      pollTaskStatus(id)
    }, 2000)
  }

  // 上传订单文件
  const handleUploadOrders = async () => {
    if (!ordersFile?.originFileObj) {
      message.error('请先选择订单文件')
      return
    }

    setLoading(true)
    setTaskProgress('正在上传文件...')
    try {
      const result = await uploadApi.uploadOrders(ordersFile.originFileObj) as unknown as { task_id: string; message: string }
      message.info(result.message)
      startPolling(result.task_id)
      fetchTaskList() // 刷新任务列表
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '上传失败'
      message.error(errorMessage)
      setLoading(false)
      setTaskProgress('')
    }
  }

  // 上传售后单文件
  const handleUploadAftersales = async () => {
    if (!aftersalesFile?.originFileObj) {
      message.error('请先选择售后单文件')
      return
    }

    setLoading(true)
    setTaskProgress('正在上传文件...')
    try {
      const result = await uploadApi.uploadAftersales(aftersalesFile.originFileObj) as unknown as { task_id: string; message: string }
      message.info(result.message)
      startPolling(result.task_id)
      fetchTaskList() // 刷新任务列表
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '上传失败'
      message.error(errorMessage)
      setLoading(false)
      setTaskProgress('')
    }
  }

  // 查询物流状态
  const handleCheckLogistics = async () => {
    setLoading(true)
    try {
      // 默认不限制：由后端按批次把符合条件的订单全部处理
      await logisticsApi.checkAll()
      message.success('已启动物流状态查询任务')
      
      // 获取物流统计
      const stats = await logisticsApi.getStats() as unknown as LogisticsStats
      setLogisticsStats(stats)
      setCurrentStep(3)
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '查询失败'
      message.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // 计算统计数据
  const handleCalculateStats = async () => {
    setLoading(true)
    try {
      const result = await statsApi.calculateStats() as unknown as { count: number }
      setSkuStatsCount(result.count || 0)
      message.success(`统计计算完成: ${result.count} 个SKU`)
      setCurrentStep(4)
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '计算失败'
      message.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // 一键导入并计算
  const handleQuickImport = async () => {
    if (!ordersFile?.originFileObj || !aftersalesFile?.originFileObj) {
      message.error('请先选择订单文件和售后单文件')
      return
    }

    setLoading(true)
    setTaskProgress('正在上传文件...')
    try {
      const result = await uploadApi.uploadAll(
        ordersFile.originFileObj,
        aftersalesFile.originFileObj
      ) as unknown as { task_id: string; message: string }
      message.info(result.message)
      startPolling(result.task_id)
      fetchTaskList() // 刷新任务列表
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '处理失败'
      message.error(errorMessage)
      setLoading(false)
      setTaskProgress('')
    }
  }

  const steps = [
    {
      title: '上传订单',
      description: '导入订单Excel',
      icon: <FileExcelOutlined />,
    },
    {
      title: '上传售后单',
      description: '导入售后Excel',
      icon: <FileExcelOutlined />,
    },
    {
      title: '物流查询',
      description: '查询签收状态',
      icon: <SyncOutlined />,
    },
    {
      title: '统计计算',
      description: '计算SKU统计',
      icon: <CheckCircleOutlined />,
    },
  ]

  // 任务类型映射
  const taskTypeMap: Record<string, string> = {
    orders: '订单导入',
    aftersales: '售后单导入',
    all: '全部导入',
  }

  // 任务列表表格列配置
  const taskColumns: ColumnsType<TaskRecord> = [
    {
      title: '任务类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 100,
      render: (type: string) => taskTypeMap[type] || type,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string, record: TaskRecord) => {
        if (status === 'processing') {
          return (
            <Tag icon={<LoadingOutlined spin />} color="processing">
              {record.progress || '处理中'}
            </Tag>
          )
        } else if (status === 'completed') {
          return <Tag icon={<CheckCircleOutlined />} color="success">已完成</Tag>
        } else if (status === 'failed') {
          return (
            <Tooltip title={record.error}>
              <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
            </Tooltip>
          )
        }
        return status
      },
    },
    {
      title: '导入结果',
      key: 'stats',
      render: (_: unknown, record: TaskRecord) => {
        const parts: string[] = []
        if (record.order_stats) {
          parts.push(`订单: ${record.order_stats.total}条 (新增${record.order_stats.created}, 更新${record.order_stats.updated})`)
        }
        if (record.aftersale_stats) {
          parts.push(`售后: ${record.aftersale_stats.total}条 (新增${record.aftersale_stats.created}, 更新${record.aftersale_stats.updated})`)
        }
        if (record.sku_stats_count) {
          parts.push(`SKU: ${record.sku_stats_count}个`)
        }
        return parts.length > 0 ? parts.join(' | ') : '-'
      },
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 160,
      render: (time: string) => {
        if (!time) return '-'
        const date = new Date(time)
        return date.toLocaleString('zh-CN')
      },
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 160,
      render: (time: string) => {
        if (!time) return '-'
        const date = new Date(time)
        return date.toLocaleString('zh-CN')
      },
    },
  ]

  return (
    <div>
      <Alert
        message="数据导入说明"
        description="请从抖店后台导出订单数据（含快递信息字段）和售后单数据，上传后系统会自动解析并计算统计数据。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Steps
        current={currentStep}
        items={steps}
        style={{ marginBottom: 32 }}
      />

      <Row gutter={24}>
        {/* 左侧：文件上传 */}
        <Col span={12}>
          <Card title="文件选择" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              <div>
                <div style={{ marginBottom: 8, color: '#8a8a8a' }}>
                  1. 订单文件（含快递信息字段）
                </div>
                <Upload
                  accept=".xlsx,.xls"
                  maxCount={1}
                  fileList={ordersFile ? [ordersFile] : []}
                  beforeUpload={() => false}
                  onChange={({ fileList }) => {
                    setOrdersFile(fileList[0] || null)
                  }}
                >
                  <Button icon={<UploadOutlined />}>选择订单文件</Button>
                </Upload>
              </div>

              <div>
                <div style={{ marginBottom: 8, color: '#8a8a8a' }}>
                  2. 售后单文件
                </div>
                <Upload
                  accept=".xlsx,.xls"
                  maxCount={1}
                  fileList={aftersalesFile ? [aftersalesFile] : []}
                  beforeUpload={() => false}
                  onChange={({ fileList }) => {
                    setAftersalesFile(fileList[0] || null)
                  }}
                >
                  <Button icon={<UploadOutlined />}>选择售后单文件</Button>
                </Upload>
              </div>
            </Space>

            <Divider />

            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                type="primary"
                icon={<CloudUploadOutlined />}
                onClick={handleQuickImport}
                loading={loading}
                disabled={!ordersFile || !aftersalesFile || loading}
                size="large"
                block
              >
                一键导入并计算
              </Button>

              <Button
                icon={<CheckCircleOutlined />}
                onClick={handleCalculateStats}
                loading={loading}
                disabled={loading}
                block
              >
                重新计算统计（不重新导入）
              </Button>
              
              {loading && taskProgress && (
                <Alert
                  message={
                    <Space>
                      <LoadingOutlined spin />
                      <span>{taskProgress}</span>
                    </Space>
                  }
                  description="大量数据导入需要一些时间，请耐心等待..."
                  type="info"
                />
              )}
            </Space>
          </Card>

          {/* 分步操作 */}
          <Card title="分步操作" size="small">
            <Space wrap>
              <Button
                onClick={handleUploadOrders}
                loading={loading && currentStep === 0}
                disabled={!ordersFile}
              >
                1. 导入订单
              </Button>
              <Button
                onClick={handleUploadAftersales}
                loading={loading && currentStep === 1}
                disabled={!aftersalesFile || currentStep < 1}
              >
                2. 导入售后单
              </Button>
              <Button
                onClick={handleCheckLogistics}
                loading={loading && currentStep === 2}
                disabled={currentStep < 2}
              >
                3. 查询物流
              </Button>
              <Button
                onClick={handleCalculateStats}
                loading={loading && currentStep === 3}
                disabled={loading}
              >
                4. 计算统计
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 右侧：导入结果 */}
        <Col span={12}>
          <Card title="导入结果">
            {orderStats && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ color: '#fe2c55' }}>订单导入</h4>
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic title="总数" value={orderStats.total} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="新增" value={orderStats.created} valueStyle={{ color: '#52c41a' }} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="更新" value={orderStats.updated} valueStyle={{ color: '#1890ff' }} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="跳过" value={orderStats.skipped} valueStyle={{ color: '#8a8a8a' }} />
                  </Col>
                </Row>
              </div>
            )}

            {aftersaleStats && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ color: '#faad14' }}>售后单导入</h4>
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic title="总数" value={aftersaleStats.total} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="新增" value={aftersaleStats.created} valueStyle={{ color: '#52c41a' }} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="更新" value={aftersaleStats.updated} valueStyle={{ color: '#1890ff' }} />
                  </Col>
                  <Col span={6}>
                    <Statistic title="跳过" value={aftersaleStats.skipped} valueStyle={{ color: '#8a8a8a' }} />
                  </Col>
                </Row>
              </div>
            )}

            {logisticsStats && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ color: '#52c41a' }}>物流状态</h4>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic title="有物流单号" value={logisticsStats.with_logistics} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="已签收" value={logisticsStats.signed} valueStyle={{ color: '#52c41a' }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="待查询" value={logisticsStats.pending_check} valueStyle={{ color: '#faad14' }} />
                  </Col>
                </Row>
              </div>
            )}

            {skuStatsCount > 0 && (
              <div>
                <h4 style={{ color: '#1890ff' }}>统计计算</h4>
                <Statistic 
                  title="SKU统计数" 
                  value={skuStatsCount} 
                  suffix="个SKU"
                  valueStyle={{ color: '#1890ff' }}
                />
              </div>
            )}

            {!orderStats && !aftersaleStats && (
              <div style={{ color: '#8a8a8a', textAlign: 'center', padding: 40 }}>
                请先上传文件并导入数据
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 任务历史列表 */}
      <Card 
        title={
          <Space>
            <ClockCircleOutlined />
            <span>导入任务历史（最近15条）</span>
          </Space>
        }
        extra={
          <Button 
            icon={<ReloadOutlined />} 
            onClick={fetchTaskList}
            loading={taskListLoading}
          >
            刷新
          </Button>
        }
        style={{ marginTop: 24 }}
      >
        <Table
          columns={taskColumns}
          dataSource={taskList}
          rowKey="task_id"
          loading={taskListLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无导入任务记录' }}
        />
      </Card>
    </div>
  )
}
