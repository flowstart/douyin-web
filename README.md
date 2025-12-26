# 抖音订单统计系统

基于抖音开放平台的订单数据统计和分析系统，支持按 SKU 维度进行订单、售后、物流数据的统计分析。

## 功能特性

- **SKU 统计看板**：待发货量、售后未完结、已签收数量、预估退货率、商品缺口预警
- **时间筛选**：支持按时间区间查询订单数据
- **智能排序**：支持按各指标排序，快速定位问题 SKU
- **退货率分析**：自动计算退货率，支持手动修改
- **省份维度分析**：按省份统计退货率

## 技术栈

### 后端
- Python 3.11+
- FastAPI
- SQLAlchemy (异步)
- SQLite / MySQL

### 前端
- React 18
- Next.js 14
- Ant Design 5
- TypeScript

## 项目结构

```
douyin-web/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务服务
│   │   ├── config.py       # 配置管理
│   │   ├── database.py     # 数据库连接
│   │   └── main.py         # 应用入口
│   ├── requirements.txt    # Python 依赖
│   └── env.example         # 环境变量示例
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── app/           # Next.js 页面
│   │   ├── components/    # React 组件
│   │   ├── lib/           # 工具库
│   │   └── types/         # TypeScript 类型
│   └── package.json       # Node.js 依赖
└── README.md
```

## 快速开始

### 1. 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入抖音开放平台凭证

# 启动服务
python -m app.main
# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 3. 访问应用

- 前端页面: http://localhost:3000
- 后端 API 文档: http://localhost:8000/docs

## 抖音开放平台配置

1. 访问 [抖音电商开放平台](https://op.jinritemai.com/)
2. 创建应用，获取 App Key 和 App Secret
3. 申请相关 API 权限：
   - order.searchList
   - order.orderDetail
   - afterSale.List
   - afterSale.Detail
   - logistics.trackNoRouteDetail
4. 将凭证填入 `.env` 文件

## API 接口

### 统计接口

- `GET /api/stats/sku` - 获取 SKU 统计列表
- `POST /api/stats/sku/calculate` - 重新计算统计
- `PUT /api/stats/sku/{sku_code}/return-rate` - 更新退货率
- `GET /api/stats/province` - 获取省份统计

### 数据同步接口

- `POST /api/sync/orders` - 同步订单数据
- `POST /api/sync/aftersales` - 同步售后数据
- `POST /api/sync/all` - 全量同步

### 订单接口

- `GET /api/orders` - 获取订单列表
- `GET /api/orders/{order_id}` - 获取订单详情

## 统计指标说明

| 指标 | 说明 |
|------|------|
| 待发货量 | 订单状态为"待发货"的 SKU 数量 |
| 售后未完结 | 状态为"待买家寄货"或"待商家收货"的售后单数量 |
| 已签收数量 | 近 90 天物流状态为已签收的订单 SKU 数量 |
| 预估退货率 | 已签收订单的退货数 / 已签收数量（<10单默认30%） |
| 在途未签收 | 已发货但物流未签收的订单数量 |
| 预估商品缺口 | 待发货量 - 售后未完结 - 在途预估退货数量 |

