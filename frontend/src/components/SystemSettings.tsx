'use client'

import { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Input,
  InputNumber,
  Button,
  message,
  Spin,
  Space,
  Divider,
  Alert,
  Typography,
} from 'antd'
import {
  SaveOutlined,
  ApiOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import { configApi } from '@/lib/api'

const { Text } = Typography

interface ConfigItem {
  config_key: string
  config_value: string
  description: string
}

export default function SystemSettings() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // 加载配置
  const loadConfigs = async () => {
    setLoading(true)
    try {
      const configs = await configApi.getAll() as ConfigItem[]
      
      // 转换为表单数据
      const formData: Record<string, string | number> = {}
      configs.forEach((config) => {
        if (config.config_key === 'logistics_query_interval') {
          formData[config.config_key] = parseInt(config.config_value) || 35
        } else {
          formData[config.config_key] = config.config_value
        }
      })
      
      form.setFieldsValue(formData)
    } catch (error) {
      console.error('加载配置失败:', error)
      message.error('加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConfigs()
  }, [])

  // 保存配置
  const handleSave = async (values: Record<string, string | number>) => {
    setSaving(true)
    try {
      const configs = [
        {
          config_key: 'kd100_customer',
          config_value: String(values.kd100_customer || ''),
          description: '快递100 Customer ID',
        },
        {
          config_key: 'kd100_key',
          config_value: String(values.kd100_key || ''),
          description: '快递100 API Key',
        },
        {
          config_key: 'logistics_query_interval',
          config_value: String(values.logistics_query_interval || 35),
          description: '同一物流单号查询间隔（分钟）',
        },
      ]
      
      await configApi.batchUpdate(configs)
      message.success('配置保存成功')
    } catch (error) {
      console.error('保存配置失败:', error)
      message.error('保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Spin spinning={loading}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          logistics_query_interval: 35,
        }}
      >
        {/* 快递100 配置 */}
        <Card
          title={
            <Space>
              <ApiOutlined />
              <span>快递100 API 配置</span>
            </Space>
          }
          style={{ marginBottom: 24 }}
        >
          <Alert
            message="快递100 API 用于查询物流签收状态"
            description={
              <div>
                <p>请前往 <a href="https://www.kuaidi100.com/openapi/" target="_blank" rel="noopener noreferrer">快递100开放平台</a> 注册并获取 API 密钥。</p>
                <p>授权参数说明：</p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  <li><Text code>Customer</Text>：企业编号（customer参数）</li>
                  <li><Text code>Key</Text>：授权密钥（用于签名验证）</li>
                </ul>
              </div>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          
          <Form.Item
            name="kd100_customer"
            label="Customer ID"
            rules={[{ required: true, message: '请输入 Customer ID' }]}
          >
            <Input placeholder="例如: 9B7C2D0C2860E99183679B392B0B0F2B" />
          </Form.Item>
          
          <Form.Item
            name="kd100_key"
            label="API Key"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder="例如: DJXAhPNm2547" />
          </Form.Item>
        </Card>

        {/* 物流查询配置 */}
        <Card
          title={
            <Space>
              <ClockCircleOutlined />
              <span>物流查询配置</span>
            </Space>
          }
          style={{ marginBottom: 24 }}
        >
          <Alert
            message="重要提示：控制查询频率，避免锁单"
            description="快递100 对同一物流单号的查询有频率限制。请将查询间隔设置在 30 分钟以上，否则可能会导致锁单。"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
          
          <Form.Item
            name="logistics_query_interval"
            label="单号查询间隔（分钟）"
            rules={[
              { required: true, message: '请输入查询间隔' },
              { type: 'number', min: 30, message: '查询间隔不能小于30分钟' },
            ]}
            extra="同一物流单号在间隔时间内不会重复查询，默认35分钟"
          >
            <InputNumber min={30} max={1440} style={{ width: 200 }} />
          </Form.Item>
        </Card>

        <Divider />

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined />}
            loading={saving}
            size="large"
          >
            保存配置
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  )
}

