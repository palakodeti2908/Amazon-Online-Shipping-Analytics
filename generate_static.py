"""
Generates a single self-contained dashboard.html with all analytics data embedded.
Open the resulting file directly in Chrome — no server required.
"""
import pandas as pd
import numpy as np
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Dataset')

orders = pd.read_csv(f'{DATA_DIR}/orders.csv')
order_details = pd.read_csv(f'{DATA_DIR}/order_details.csv')
customers = pd.read_csv(f'{DATA_DIR}/customers.csv')
products = pd.read_csv(f'{DATA_DIR}/products.csv')
employees = pd.read_csv(f'{DATA_DIR}/employee.csv')
shippers = pd.read_csv(f'{DATA_DIR}/shippers.csv')
categories = pd.read_csv(f'{DATA_DIR}/categories.csv')

for col in ['orderDate', 'requiredDate', 'shippedDate']:
    orders[col] = pd.to_datetime(orders[col], dayfirst=True, errors='coerce')

order_details = order_details.copy()
order_details['revenue'] = (
    order_details['unitPrice'] * order_details['quantity'] * (1 - order_details['discount'])
)

od = order_details.merge(
    orders[['orderID', 'customerID', 'employeeID', 'orderDate', 'requiredDate',
            'shippedDate', 'shipVia', 'freight', 'shipCountry']],
    on='orderID', how='left'
)
od = od.merge(products[['productID', 'productName', 'categoryID']], on='productID', how='left')
od = od.merge(categories[['categoryID', 'categoryName']], on='categoryID', how='left')
od = od.merge(customers[['customerID', 'contactName']], on='customerID', how='left')
od = od.merge(employees[['employeeID', 'firstName', 'lastName']], on='employeeID', how='left')
od['employeeName'] = od['firstName'].fillna('') + ' ' + od['lastName'].fillna('')
od = od.merge(shippers[['shipperID', 'companyName']], left_on='shipVia', right_on='shipperID', how='left')
od.rename(columns={'companyName': 'shipperName'}, inplace=True)

def j(obj):
    return json.dumps(obj)

# KPIs
total_orders = int(orders['orderID'].nunique())
total_revenue = round(float(od['revenue'].sum()), 2)
avg_freight = round(float(orders['freight'].mean()), 2)
total_customers = int(customers['customerID'].nunique())
shipped = orders.dropna(subset=['shippedDate'])
on_time = int((shipped['shippedDate'] <= shipped['requiredDate']).sum())
on_time_rate = round(on_time / len(shipped) * 100, 1) if len(shipped) > 0 else 0
avg_order_value = round(float(od.groupby('orderID')['revenue'].sum().mean()), 2)

# Time series
df = orders.copy()
df['yearMonth'] = df['orderDate'].dt.to_period('M').astype(str)
monthly_orders = df.groupby('yearMonth')['orderID'].count().reset_index()
monthly_orders.columns = ['yearMonth', 'orderCount']
od2 = od.copy()
od2['yearMonth'] = od2['orderDate'].dt.to_period('M').astype(str)
monthly_rev = od2.groupby('yearMonth')['revenue'].sum().reset_index()
monthly = monthly_orders.merge(monthly_rev, on='yearMonth', how='left').sort_values('yearMonth')
ts_labels = monthly['yearMonth'].tolist()
ts_orders = monthly['orderCount'].tolist()
ts_revenue = [round(v, 2) for v in monthly['revenue'].fillna(0).tolist()]

# Category revenue
cat_rev = od.groupby('categoryName')['revenue'].sum().sort_values(ascending=False)
cat_labels = cat_rev.index.tolist()
cat_values = [round(v, 2) for v in cat_rev.tolist()]

# Delivery status
late = int((shipped['shippedDate'] > shipped['requiredDate']).sum())
pending = int(orders['shippedDate'].isna().sum())

# Revenue by country (top 15, ascending for horizontal bar)
country_rev = od.groupby('shipCountry')['revenue'].sum().sort_values(ascending=True).tail(15)
country_labels = country_rev.index.tolist()
country_values = [round(v, 2) for v in country_rev.tolist()]

# Top customers (top 10, ascending)
cust_rev = od.groupby('contactName')['revenue'].sum().sort_values(ascending=True).tail(10)
cust_labels = cust_rev.index.tolist()
cust_values = [round(v, 2) for v in cust_rev.tolist()]

# Employee performance
emp_data = od.groupby('employeeName').agg(
    revenue=('revenue', 'sum'),
    orderCount=('orderID', 'nunique')
).sort_values('revenue', ascending=False).reset_index()
emp_labels = emp_data['employeeName'].tolist()
emp_revenue = [round(v, 2) for v in emp_data['revenue'].tolist()]
emp_orders = emp_data['orderCount'].tolist()

# Shipper performance
shipped_with = orders.dropna(subset=['shippedDate']).merge(
    shippers[['shipperID', 'companyName']], left_on='shipVia', right_on='shipperID', how='left'
)
shipped_with['onTime'] = shipped_with['shippedDate'] <= shipped_with['requiredDate']
ship_stats = shipped_with.groupby('companyName').agg(
    orderCount=('orderID', 'count'),
    avgFreight=('freight', 'mean'),
    onTimeRate=('onTime', 'mean')
).reset_index()
ship_stats['onTimeRate'] = (ship_stats['onTimeRate'] * 100).round(1)
all_shippers = orders.merge(
    shippers[['shipperID', 'companyName']], left_on='shipVia', right_on='shipperID', how='left'
).groupby('companyName')['orderID'].count().reset_index()
all_shippers.columns = ['companyName', 'totalOrders']
ship_stats = ship_stats.merge(all_shippers, on='companyName', how='left')
ship_labels = ship_stats['companyName'].tolist()
ship_orders = ship_stats['totalOrders'].tolist()
ship_freight = [round(v, 2) for v in ship_stats['avgFreight'].tolist()]
ship_ontime = ship_stats['onTimeRate'].tolist()

# Top products (top 10, ascending)
prod_rev = od.groupby('productName')['revenue'].sum().sort_values(ascending=True).tail(10)
prod_labels = prod_rev.index.tolist()
prod_values = [round(v, 2) for v in prod_rev.tolist()]

# Freight trend
mf = orders.copy()
mf['yearMonth'] = mf['orderDate'].dt.to_period('M').astype(str)
mf_agg = mf.groupby('yearMonth')['freight'].agg(['sum', 'mean']).reset_index()
mf_agg.columns = ['yearMonth', 'totalFreight', 'avgFreight']
mf_agg = mf_agg.sort_values('yearMonth')
ft_labels = mf_agg['yearMonth'].tolist()
ft_total = [round(v, 2) for v in mf_agg['totalFreight'].tolist()]

# Freight by country (top 15, ascending)
fc = orders.groupby('shipCountry').agg(
    totalFreight=('freight', 'sum'),
    orderCount=('orderID', 'count')
).sort_values('totalFreight', ascending=True).tail(15)
fc_labels = fc.index.tolist()
fc_freight = [round(v, 2) for v in fc['totalFreight'].tolist()]
fc_orders = fc['orderCount'].tolist()

# Inventory
inv = products[['productName', 'unitsInStock', 'unitsOnOrder', 'reorderLevel']].sort_values(
    'unitsInStock', ascending=False
).head(15)
inv_labels = inv['productName'].tolist()
inv_stock = inv['unitsInStock'].tolist()
inv_order = inv['unitsOnOrder'].tolist()

# Orders by country (top 15, ascending)
obc = orders.groupby('shipCountry')['orderID'].count().sort_values(ascending=True).tail(15)
obc_labels = obc.index.tolist()
obc_values = obc.tolist()

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Amazon Shipping Analytics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--orange:#FF9900;--navy:#232F3E;--sidebar-bg:#1a2035;--sidebar-hover:#232b42;--orange-bg:rgba(255,153,0,.14);--sidebar-text:#8892b0;--bg:#f1f5f9;--card:#ffffff;--text:#1e293b;--text-2:#64748b;--border:#e2e8f0;--shadow:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.05);--shadow-md:0 4px 12px rgba(0,0,0,.1);--radius:12px}}
html,body{{height:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text)}}
.app{{display:flex;height:100vh;overflow:hidden}}
.sidebar{{width:220px;background:var(--sidebar-bg);display:flex;flex-direction:column;flex-shrink:0;transition:width .25s;overflow:hidden;z-index:100}}
.sidebar.collapsed{{width:62px}}
.sidebar.collapsed .brand-text,.sidebar.collapsed .nav-item span,.sidebar.collapsed .sidebar-footer{{opacity:0;pointer-events:none}}
.sidebar-brand{{display:flex;align-items:center;gap:10px;padding:20px 16px;border-bottom:1px solid rgba(255,255,255,.05)}}
.brand-text{{color:#fff;font-weight:700;font-size:15px;white-space:nowrap}}
.sidebar-nav{{display:flex;flex-direction:column;gap:4px;padding:12px 10px;flex:1}}
.nav-item{{display:flex;align-items:center;gap:10px;padding:10px 12px;border:none;background:transparent;color:var(--sidebar-text);border-radius:8px;cursor:pointer;font-size:14px;font-weight:500;transition:all .15s;white-space:nowrap;width:100%;text-align:left}}
.nav-item svg{{width:18px;height:18px;flex-shrink:0}}
.nav-item:hover{{background:var(--sidebar-hover);color:#c8d3ea}}
.nav-item.active{{background:var(--orange-bg);color:var(--orange)}}
.nav-item.active svg{{stroke:var(--orange)}}
.sidebar-footer{{padding:12px 16px 16px;border-top:1px solid rgba(255,255,255,.05)}}
.data-period{{display:flex;align-items:center;gap:6px;color:#5a6480;font-size:11px}}
.main-content{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{height:60px;background:var(--card);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 24px;flex-shrink:0;box-shadow:var(--shadow)}}
.topbar-left{{display:flex;align-items:center;gap:12px}}
.menu-btn{{background:none;border:none;cursor:pointer;color:var(--text-2);padding:4px;border-radius:6px;display:flex}}
.menu-btn:hover{{background:var(--bg)}}
.menu-btn svg,.topbar-left svg{{width:20px;height:20px}}
.page-title{{font-size:18px;font-weight:700;color:var(--text)}}
.amazon-badge{{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:6px 14px;font-size:13px;font-weight:600;color:var(--navy)}}
.page-container{{flex:1;overflow-y:auto;padding:24px}}
.page-container::-webkit-scrollbar{{width:6px}}
.page-container::-webkit-scrollbar-thumb{{background:#cbd5e1;border-radius:3px}}
.page{{display:none}}
.page.active{{display:block}}
.kpi-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}}
.kpi-card{{background:var(--card);border-radius:var(--radius);padding:20px;display:flex;align-items:center;gap:16px;box-shadow:var(--shadow);border:1px solid var(--border);transition:transform .2s,box-shadow .2s}}
.kpi-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow-md)}}
.kpi-icon{{width:48px;height:48px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.kpi-icon svg{{width:22px;height:22px}}
.kpi-card[data-c="orange"] .kpi-icon{{background:rgba(255,153,0,.12)}} .kpi-card[data-c="orange"] .kpi-icon svg{{stroke:#FF9900}} .kpi-card[data-c="orange"] .kpi-value{{color:#FF9900}}
.kpi-card[data-c="blue"] .kpi-icon{{background:rgba(20,110,180,.12)}} .kpi-card[data-c="blue"] .kpi-icon svg{{stroke:#146EB4}} .kpi-card[data-c="blue"] .kpi-value{{color:#146EB4}}
.kpi-card[data-c="green"] .kpi-icon{{background:rgba(34,197,94,.12)}} .kpi-card[data-c="green"] .kpi-icon svg{{stroke:#22c55e}} .kpi-card[data-c="green"] .kpi-value{{color:#22c55e}}
.kpi-card[data-c="purple"] .kpi-icon{{background:rgba(139,92,246,.12)}} .kpi-card[data-c="purple"] .kpi-icon svg{{stroke:#8b5cf6}} .kpi-card[data-c="purple"] .kpi-value{{color:#8b5cf6}}
.kpi-card[data-c="teal"] .kpi-icon{{background:rgba(20,184,166,.12)}} .kpi-card[data-c="teal"] .kpi-icon svg{{stroke:#14b8a6}} .kpi-card[data-c="teal"] .kpi-value{{color:#14b8a6}}
.kpi-card[data-c="amber"] .kpi-icon{{background:rgba(245,158,11,.12)}} .kpi-card[data-c="amber"] .kpi-icon svg{{stroke:#f59e0b}} .kpi-card[data-c="amber"] .kpi-value{{color:#f59e0b}}
.kpi-value{{font-size:26px;font-weight:800;line-height:1;margin-bottom:4px;letter-spacing:-0.5px}}
.kpi-label{{font-size:12px;color:var(--text-2);font-weight:500;text-transform:uppercase;letter-spacing:0.5px}}
.charts-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}
.chart-card{{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border);overflow:hidden}}
.chart-card.span-2{{grid-column:span 2}}
.chart-header{{padding:16px 20px 12px;border-bottom:1px solid var(--border)}}
.chart-header h3{{font-size:14px;font-weight:600;color:var(--text)}}
.chart-body{{padding:16px 20px 20px;position:relative;height:300px}}
.chart-body-sm{{height:260px}}
.chart-body-tall{{height:420px}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar" id="sidebar">
  <div class="sidebar-brand">
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="6" fill="#FF9900"/><path d="M7 14h14M14 7v14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/><circle cx="14" cy="14" r="4" stroke="#fff" stroke-width="2"/></svg>
    <span class="brand-text">ShipAnalytics</span>
  </div>
  <nav class="sidebar-nav">
    <button class="nav-item active" data-page="overview"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg><span>Overview</span></button>
    <button class="nav-item" data-page="orders"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/></svg><span>Orders</span></button>
    <button class="nav-item" data-page="revenue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg><span>Revenue</span></button>
    <button class="nav-item" data-page="shipping"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13" rx="1"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg><span>Shipping</span></button>
    <button class="nav-item" data-page="products"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg><span>Products</span></button>
    <button class="nav-item" data-page="team"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg><span>Team</span></button>
  </nav>
  <div class="sidebar-footer">
    <div class="data-period"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg><span>830 Orders &bull; 91 Customers</span></div>
  </div>
</aside>
<main class="main-content">
  <header class="topbar">
    <div class="topbar-left">
      <button class="menu-btn" id="menuBtn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
      <h1 class="page-title" id="pageTitle">Overview</h1>
    </div>
    <div class="topbar-right">
      <div class="amazon-badge"><svg width="20" height="20" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="6" fill="#FF9900"/><path d="M7 14h14M14 7v14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/></svg>Amazon Shipping Analytics</div>
    </div>
  </header>
  <div class="page-container">

    <!-- OVERVIEW -->
    <div id="overview-page" class="page active">
      <div class="kpi-grid">
        <div class="kpi-card" data-c="orange"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-orders">—</div><div class="kpi-label">Total Orders</div></div></div>
        <div class="kpi-card" data-c="blue"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-revenue">—</div><div class="kpi-label">Total Revenue</div></div></div>
        <div class="kpi-card" data-c="green"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-ontime">—</div><div class="kpi-label">On-Time Rate</div></div></div>
        <div class="kpi-card" data-c="purple"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-customers">—</div><div class="kpi-label">Customers</div></div></div>
        <div class="kpi-card" data-c="teal"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13" rx="1"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-freight">—</div><div class="kpi-label">Avg Freight</div></div></div>
        <div class="kpi-card" data-c="amber"><div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg></div><div class="kpi-content"><div class="kpi-value" id="kv-aov">—</div><div class="kpi-label">Avg Order Value</div></div></div>
      </div>
      <div class="charts-grid">
        <div class="chart-card span-2"><div class="chart-header"><h3>Orders &amp; Revenue Over Time</h3></div><div class="chart-body"><canvas id="c-ort"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Revenue by Category</h3></div><div class="chart-body chart-body-sm"><canvas id="c-cat"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Delivery Status</h3></div><div class="chart-body chart-body-sm"><canvas id="c-del"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Top Customers by Revenue</h3></div><div class="chart-body"><canvas id="c-topcust-ov"></canvas></div></div>
      </div>
    </div>

    <!-- ORDERS -->
    <div id="orders-page" class="page">
      <div class="charts-grid">
        <div class="chart-card span-2"><div class="chart-header"><h3>Monthly Order Volume</h3></div><div class="chart-body"><canvas id="c-mo"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Orders by Destination Country (Top 15)</h3></div><div class="chart-body chart-body-tall"><canvas id="c-obc"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Orders by Carrier</h3></div><div class="chart-body"><canvas id="c-oship"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Monthly Freight Cost</h3></div><div class="chart-body"><canvas id="c-ft"></canvas></div></div>
      </div>
    </div>

    <!-- REVENUE -->
    <div id="revenue-page" class="page">
      <div class="charts-grid">
        <div class="chart-card span-2"><div class="chart-header"><h3>Revenue Trend (Monthly)</h3></div><div class="chart-body"><canvas id="c-rtrend"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Revenue by Country (Top 15)</h3></div><div class="chart-body chart-body-tall"><canvas id="c-rbc"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Revenue by Category</h3></div><div class="chart-body"><canvas id="c-rcat"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Top 10 Customers</h3></div><div class="chart-body"><canvas id="c-topcust"></canvas></div></div>
      </div>
    </div>

    <!-- SHIPPING -->
    <div id="shipping-page" class="page">
      <div class="charts-grid">
        <div class="chart-card"><div class="chart-header"><h3>Delivery Status</h3></div><div class="chart-body chart-body-sm"><canvas id="c-dellg"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Carrier On-Time Rate</h3></div><div class="chart-body chart-body-sm"><canvas id="c-sot"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Shipper — Orders &amp; Avg Freight</h3></div><div class="chart-body"><canvas id="c-scmp"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Freight Cost by Country (Top 15)</h3></div><div class="chart-body chart-body-tall"><canvas id="c-fbc"></canvas></div></div>
      </div>
    </div>

    <!-- PRODUCTS -->
    <div id="products-page" class="page">
      <div class="charts-grid">
        <div class="chart-card span-2"><div class="chart-header"><h3>Top 10 Products by Revenue</h3></div><div class="chart-body chart-body-tall"><canvas id="c-tprod"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Revenue by Category</h3></div><div class="chart-body"><canvas id="c-pcatbar"></canvas></div></div>
        <div class="chart-card"><div class="chart-header"><h3>Inventory Levels (Top 15)</h3></div><div class="chart-body"><canvas id="c-inv"></canvas></div></div>
      </div>
    </div>

    <!-- TEAM -->
    <div id="team-page" class="page">
      <div class="charts-grid">
        <div class="chart-card span-2"><div class="chart-header"><h3>Revenue by Employee</h3></div><div class="chart-body"><canvas id="c-erev"></canvas></div></div>
        <div class="chart-card span-2"><div class="chart-header"><h3>Orders Handled by Employee</h3></div><div class="chart-body"><canvas id="c-eord"></canvas></div></div>
      </div>
    </div>

  </div>
</main>
</div>

<script>
const C=['#FF9900','#146EB4','#22c55e','#8b5cf6','#ef4444','#14b8a6','#f59e0b','#ec4899','#6366f1','#06b6d4','#84cc16','#f97316','#0ea5e9','#a855f7','#10b981'];
const PAGES={{'overview':'Overview','orders':'Orders','revenue':'Revenue','shipping':'Shipping Performance','products':'Products','team':'Team Performance'}};

// Embedded data
const D={{
  ts_labels:{j(ts_labels)},ts_orders:{j(ts_orders)},ts_revenue:{j(ts_revenue)},
  cat_labels:{j(cat_labels)},cat_values:{j(cat_values)},
  on_time:{on_time},late:{late},pending:{pending},
  country_labels:{j(country_labels)},country_values:{j(country_values)},
  cust_labels:{j(cust_labels)},cust_values:{j(cust_values)},
  emp_labels:{j(emp_labels)},emp_revenue:{j(emp_revenue)},emp_orders:{j(emp_orders)},
  ship_labels:{j(ship_labels)},ship_orders:{j(ship_orders)},ship_freight:{j(ship_freight)},ship_ontime:{j(ship_ontime)},
  prod_labels:{j(prod_labels)},prod_values:{j(prod_values)},
  ft_labels:{j(ft_labels)},ft_total:{j(ft_total)},
  fc_labels:{j(fc_labels)},fc_freight:{j(fc_freight)},
  inv_labels:{j(inv_labels)},inv_stock:{j(inv_stock)},inv_order:{j(inv_order)},
  obc_labels:{j(obc_labels)},obc_values:{j(obc_values)},
  total_orders:{total_orders},total_revenue:{total_revenue},avg_freight:{avg_freight},
  total_customers:{total_customers},on_time_rate:{on_time_rate},avg_order_value:{avg_order_value}
}};

function fmt(n,pre='',suf=''){{
  if(n>=1e6) return pre+(n/1e6).toFixed(2)+'M'+suf;
  if(n>=1e3) return pre+(n/1e3).toFixed(1)+'K'+suf;
  return pre+n.toLocaleString('en-US',{{minimumFractionDigits:0,maximumFractionDigits:1}})+suf;
}}

function animVal(el,end,pre='',suf=''){{
  const dur=900,t0=performance.now();
  function step(t){{const p=Math.min((t-t0)/dur,1),e=1-Math.pow(1-p,3),v=end*e;el.textContent=fmt(v,pre,suf);if(p<1)requestAnimationFrame(step);else el.textContent=fmt(end,pre,suf);}}
  requestAnimationFrame(step);
}}

const TT={{backgroundColor:'#1e293b',titleColor:'#f8fafc',bodyColor:'#cbd5e1',borderColor:'#334155',borderWidth:1,padding:10,cornerRadius:8}};
const GRID={{color:'#f1f5f9'}};
const TICKS={{color:'#64748b',font:{{size:11}}}};

function mk(id,type,data,opts){{
  const ctx=document.getElementById(id);
  if(!ctx)return;
  return new Chart(ctx,{{type,data,options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{font:{{size:12}},color:'#64748b',boxWidth:12,padding:12}}}},tooltip:TT}},...opts}}}});
}}

const charts={{}};
const loaded={{}};

function initOverview(){{
  animVal(document.getElementById('kv-orders'),D.total_orders);
  animVal(document.getElementById('kv-revenue'),D.total_revenue,'$');
  animVal(document.getElementById('kv-ontime'),D.on_time_rate,'','%');
  animVal(document.getElementById('kv-customers'),D.total_customers);
  animVal(document.getElementById('kv-freight'),D.avg_freight,'$');
  animVal(document.getElementById('kv-aov'),D.avg_order_value,'$');

  charts['ort']=mk('c-ort','line',{{labels:D.ts_labels,datasets:[
    {{label:'Revenue ($)',data:D.ts_revenue,borderColor:'#FF9900',backgroundColor:'rgba(255,153,0,.1)',fill:true,tension:.4,yAxisID:'y',pointRadius:3,pointHoverRadius:6}},
    {{label:'Orders',data:D.ts_orders,borderColor:'#146EB4',backgroundColor:'transparent',tension:.4,yAxisID:'y1',borderDash:[5,3],pointRadius:3,pointHoverRadius:6}}
  ]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{position:'left',grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:TICKS}}}}}});

  charts['cat']=mk('c-cat','doughnut',{{labels:D.cat_labels,datasets:[{{data:D.cat_values,backgroundColor:C,borderWidth:2,borderColor:'#fff'}}]}},{{cutout:'62%'}});
  charts['del']=mk('c-del','doughnut',{{labels:['On Time','Late','Pending'],datasets:[{{data:[D.on_time,D.late,D.pending],backgroundColor:['#22c55e','#ef4444','#f59e0b'],borderWidth:2,borderColor:'#fff'}}]}},{{cutout:'62%'}});

  charts['topcust-ov']=mk('c-topcust-ov','bar',{{labels:D.cust_labels,datasets:[{{label:'Revenue ($)',data:D.cust_values,backgroundColor:C.slice(0,D.cust_labels.length),borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
}}

function initOrders(){{
  charts['mo']=mk('c-mo','bar',{{labels:D.ts_labels,datasets:[{{label:'Orders',data:D.ts_orders,backgroundColor:'rgba(255,153,0,.8)',borderRadius:5}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
  charts['obc']=mk('c-obc','bar',{{labels:D.obc_labels,datasets:[{{label:'Orders',data:D.obc_values,backgroundColor:'rgba(20,110,180,.8)',borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
  charts['oship']=mk('c-oship','bar',{{labels:D.ship_labels,datasets:[{{label:'Total Orders',data:D.ship_orders,backgroundColor:C.slice(0,3),borderRadius:8}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
  charts['ft']=mk('c-ft','line',{{labels:D.ft_labels,datasets:[{{label:'Freight ($)',data:D.ft_total,borderColor:'#14b8a6',backgroundColor:'rgba(20,184,166,.1)',fill:true,tension:.4,pointRadius:3}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}}}},plugins:{{legend:{{display:false}}}}}});
}}

function initRevenue(){{
  charts['rtrend']=mk('c-rtrend','line',{{labels:D.ts_labels,datasets:[{{label:'Revenue ($)',data:D.ts_revenue,borderColor:'#FF9900',backgroundColor:'rgba(255,153,0,.15)',fill:true,tension:.4,pointRadius:4,pointHoverRadius:7}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}}}},plugins:{{legend:{{display:false}}}}}});
  charts['rbc']=mk('c-rbc','bar',{{labels:D.country_labels,datasets:[{{label:'Revenue ($)',data:D.country_values,backgroundColor:'rgba(255,153,0,.85)',borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
  charts['rcat']=mk('c-rcat','bar',{{labels:D.cat_labels,datasets:[{{label:'Revenue ($)',data:D.cat_values,backgroundColor:C.slice(0,D.cat_labels.length),borderRadius:6}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}}}},plugins:{{legend:{{display:false}}}}}});
  charts['topcust']=mk('c-topcust','bar',{{labels:D.cust_labels,datasets:[{{label:'Revenue ($)',data:D.cust_values,backgroundColor:'rgba(139,92,246,.8)',borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
}}

function initShipping(){{
  charts['dellg']=mk('c-dellg','doughnut',{{labels:['On Time','Late','Pending'],datasets:[{{data:[D.on_time,D.late,D.pending],backgroundColor:['#22c55e','#ef4444','#f59e0b'],borderWidth:3,borderColor:'#fff'}}]}},{{cutout:'65%'}});
  charts['sot']=mk('c-sot','bar',{{labels:D.ship_labels,datasets:[{{label:'On-Time %',data:D.ship_ontime,backgroundColor:['#22c55e','#14b8a6','#3b82f6'],borderRadius:8}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>v+'%'}},suggestedMax:100}}}},plugins:{{legend:{{display:false}}}}}});
  charts['scmp']=mk('c-scmp','bar',{{labels:D.ship_labels,datasets:[
    {{label:'Orders',data:D.ship_orders,backgroundColor:'rgba(255,153,0,.85)',borderRadius:5,yAxisID:'y'}},
    {{label:'Avg Freight ($)',data:D.ship_freight,backgroundColor:'rgba(20,110,180,.75)',borderRadius:5,yAxisID:'y1'}}
  ]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{position:'left',grid:GRID,ticks:TICKS}},y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{...TICKS,callback:v=>'$'+v}}}}}}}});
  charts['fbc']=mk('c-fbc','bar',{{labels:D.fc_labels,datasets:[{{label:'Total Freight ($)',data:D.fc_freight,backgroundColor:'rgba(20,184,166,.8)',borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
}}

function initProducts(){{
  charts['tprod']=mk('c-tprod','bar',{{labels:D.prod_labels,datasets:[{{label:'Revenue ($)',data:D.prod_values,backgroundColor:'rgba(255,153,0,.85)',borderRadius:5}}]}},{{indexAxis:'y',scales:{{x:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}},y:{{grid:{{display:false}},ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
  charts['pcatbar']=mk('c-pcatbar','bar',{{labels:D.cat_labels,datasets:[{{label:'Revenue ($)',data:D.cat_values,backgroundColor:C.slice(0,D.cat_labels.length),borderRadius:6}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}}}},plugins:{{legend:{{display:false}}}}}});
  charts['inv']=mk('c-inv','bar',{{labels:D.inv_labels,datasets:[
    {{label:'In Stock',data:D.inv_stock,backgroundColor:'rgba(34,197,94,.8)',borderRadius:4}},
    {{label:'On Order',data:D.inv_order,backgroundColor:'rgba(59,130,246,.8)',borderRadius:4}}
  ]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:TICKS}}}}}});
}}

function initTeam(){{
  charts['erev']=mk('c-erev','bar',{{labels:D.emp_labels,datasets:[{{label:'Revenue ($)',data:D.emp_revenue,backgroundColor:C.slice(0,D.emp_labels.length),borderRadius:8}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:{{...TICKS,callback:v=>'$'+fmt(v)}}}}}},plugins:{{legend:{{display:false}}}}}});
  charts['eord']=mk('c-eord','bar',{{labels:D.emp_labels,datasets:[{{label:'Orders',data:D.emp_orders,backgroundColor:'rgba(255,153,0,.8)',borderRadius:8}}]}},{{scales:{{x:{{grid:GRID,ticks:TICKS}},y:{{grid:GRID,ticks:TICKS}}}},plugins:{{legend:{{display:false}}}}}});
}}

const loaders={{overview:initOverview,orders:initOrders,revenue:initRevenue,shipping:initShipping,products:initProducts,team:initTeam}};

function navigate(page){{
  document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id===page+'-page'));
  document.getElementById('pageTitle').textContent=PAGES[page]||page;
  if(!loaded[page]){{loaded[page]=true;loaders[page]();}}
}}

document.addEventListener('DOMContentLoaded',()=>{{
  document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.page)));
  document.getElementById('menuBtn').addEventListener('click',()=>document.getElementById('sidebar').classList.toggle('collapsed'));
  navigate('overview');
}});
</script>
</body>
</html>"""

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"Generated: {out}")
print(f"File size: {os.path.getsize(out) / 1024:.1f} KB")
