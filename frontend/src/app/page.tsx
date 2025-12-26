'use client'

import { useState, useEffect } from 'react'
import { 
  Layout, 
  Menu, 
  theme, 
  ConfigProvider,
  Card,
  Row,
  Col,
  Statistic,
  Spin,
  Typography,
} from 'antd'
import {
  DashboardOutlined,
  ShoppingCartOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  SettingOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons'
import SkuStatsTable from '@/components/SkuStatsTable'
import DataUpload from '@/components/DataUpload'
import OrderList from '@/components/OrderList'
import SystemSettings from '@/components/SystemSettings'
import OrderTrendChart from '@/components/OrderTrendChart'
import ProvinceAnalysis from '@/components/ProvinceAnalysis'
import { statsApi } from '@/lib/api'

const { Header, Sider, Content } = Layout
const { Text } = Typography

interface StatsSummary {
  total_orders: number
  pending_ship_orders: number
  aftersale_pending_count: number
  signed_orders: number
  total_stock_gap: number
  last_import_time: string | null
  last_calculated_at: string | null
}

export default function Home() {
  const [collapsed, setCollapsed] = useState(false)
  const [selectedKey, setSelectedKey] = useState('upload')
  const [summary, setSummary] = useState<StatsSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  // 加载汇总数据
  const loadSummary = async () => {
    setSummaryLoading(true)
    try {
      const data = await statsApi.getSummary() as StatsSummary
      setSummary(data)
    } catch (error) {
      console.error('加载汇总数据失败:', error)
      setSummary(null)
    } finally {
      setSummaryLoading(false)
    }
  }

  // 切换到数据看板时加载数据
  useEffect(() => {
    if (selectedKey === 'dashboard') {
      loadSummary()
    }
  }, [selectedKey])

  // 抖音风格的深色主题
  const douyinTheme = {
    algorithm: theme.darkAlgorithm,
    token: {
      colorPrimary: '#fe2c55',
      colorBgContainer: '#1a1a1a',
      colorBgLayout: '#0f0f0f',
      colorBorder: '#2a2a2a',
      borderRadius: 8,
    },
  }

  const menuItems = [
    {
      key: 'upload',
      icon: <CloudUploadOutlined />,
      label: '数据导入',
    },
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: '数据看板',
    },
    {
      key: 'sku-stats',
      icon: <BarChartOutlined />,
      label: 'SKU统计',
    },
    {
      key: 'orders',
      icon: <ShoppingCartOutlined />,
      label: '订单管理',
    },
    {
      key: 'province',
      icon: <EnvironmentOutlined />,
      label: '省份分析',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ]

  const renderContent = () => {
    switch (selectedKey) {
      case 'upload':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              数据导入
            </h2>
            <DataUpload />
          </div>
        )
      case 'dashboard':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              数据看板
            </h2>
            <Spin spinning={summaryLoading}>
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} lg={6}>
                  <Card>
                    <Statistic
                      title="待发货订单"
                      value={summary?.pending_ship_orders ?? '-'}
                      valueStyle={{ color: '#fe2c55' }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card>
                    <Statistic
                      title="售后未完结"
                      value={summary?.aftersale_pending_count ?? '-'}
                      valueStyle={{ color: '#faad14' }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card>
                    <Statistic
                      title="已签收订单"
                      value={summary?.signed_orders ?? '-'}
                      valueStyle={{ color: '#52c41a' }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card>
                    <Statistic
                      title="商品缺口预警"
                      value={summary?.total_stock_gap ?? '-'}
                      valueStyle={{ 
                        color: (summary?.total_stock_gap ?? 0) > 0 ? '#ff4d4f' : '#52c41a' 
                      }}
                    />
                  </Card>
                </Col>
              </Row>
              {summary?.last_calculated_at && (
                <Text type="secondary" style={{ display: 'block', marginTop: 12 }}>
                  最后计算时间: {new Date(summary.last_calculated_at).toLocaleString()}
                </Text>
              )}
            </Spin>
            
            {/* 订单趋势图表 */}
            <div style={{ marginTop: 24 }}>
              <OrderTrendChart />
            </div>
            
            <Card style={{ marginTop: 24 }}>
              <h3 style={{ marginBottom: 16 }}>SKU统计概览（待发货 Top 10）</h3>
              <SkuStatsTable compact />
            </Card>
          </div>
        )
      case 'sku-stats':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              SKU统计
            </h2>
            <Card>
              <SkuStatsTable />
            </Card>
          </div>
        )
      case 'orders':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              订单管理
            </h2>
            <OrderList />
          </div>
        )
      case 'province':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              省份分析
            </h2>
            <ProvinceAnalysis />
          </div>
        )
      case 'settings':
        return (
          <div>
            <h2 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
              系统设置
            </h2>
            <SystemSettings />
          </div>
        )
      default:
        return null
    }
  }

  return (
    <ConfigProvider theme={douyinTheme}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{
            background: '#1a1a1a',
            borderRight: '1px solid #2a2a2a',
          }}
        >
          <div
            style={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderBottom: '1px solid #2a2a2a',
            }}
          >
            <span
              style={{
                color: '#fe2c55',
                fontSize: collapsed ? 18 : 20,
                fontWeight: 700,
                letterSpacing: 1,
              }}
            >
              {collapsed ? '抖' : '抖音订单统计'}
            </span>
          </div>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => setSelectedKey(key)}
            style={{ background: 'transparent', borderRight: 0 }}
          />
        </Sider>
        <Layout>
          <Header
            style={{
              background: '#1a1a1a',
              borderBottom: '1px solid #2a2a2a',
              padding: '0 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ color: '#8a8a8a' }}>
              欢迎使用抖音订单统计系统
            </span>
          </Header>
          <Content
            style={{
              margin: 24,
              padding: 24,
              minHeight: 280,
            }}
          >
            {renderContent()}
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}

