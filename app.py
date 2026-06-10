from flask import Flask, render_template, jsonify
import pandas as pd
import numpy as np
import os

app = Flask(__name__)

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


def safe_list(series):
    return [None if (isinstance(v, float) and np.isnan(v)) else v for v in series.tolist()]


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/kpis')
def get_kpis():
    total_orders = int(orders['orderID'].nunique())
    total_revenue = float(od['revenue'].sum())
    avg_freight = float(orders['freight'].mean())
    total_customers = int(customers['customerID'].nunique())

    shipped = orders.dropna(subset=['shippedDate'])
    on_time = int((shipped['shippedDate'] <= shipped['requiredDate']).sum())
    on_time_rate = round(on_time / len(shipped) * 100, 1) if len(shipped) > 0 else 0

    avg_order_value = float(od.groupby('orderID')['revenue'].sum().mean())

    return jsonify({
        'totalOrders': total_orders,
        'totalRevenue': round(total_revenue, 2),
        'avgFreight': round(avg_freight, 2),
        'totalCustomers': total_customers,
        'onTimeRate': on_time_rate,
        'avgOrderValue': round(avg_order_value, 2)
    })


@app.route('/api/orders-over-time')
def orders_over_time():
    df = orders.copy()
    df['yearMonth'] = df['orderDate'].dt.to_period('M').astype(str)
    monthly_orders = df.groupby('yearMonth')['orderID'].count().reset_index()
    monthly_orders.columns = ['yearMonth', 'orderCount']

    od2 = od.copy()
    od2['yearMonth'] = od2['orderDate'].dt.to_period('M').astype(str)
    monthly_rev = od2.groupby('yearMonth')['revenue'].sum().reset_index()

    monthly = monthly_orders.merge(monthly_rev, on='yearMonth', how='left').sort_values('yearMonth')

    return jsonify({
        'labels': monthly['yearMonth'].tolist(),
        'orderCount': monthly['orderCount'].tolist(),
        'revenue': [round(v, 2) for v in monthly['revenue'].fillna(0).tolist()]
    })


@app.route('/api/revenue-by-country')
def revenue_by_country():
    country_rev = od.groupby('shipCountry')['revenue'].sum().sort_values(ascending=True).tail(15)
    return jsonify({
        'labels': country_rev.index.tolist(),
        'values': [round(v, 2) for v in country_rev.tolist()]
    })


@app.route('/api/category-revenue')
def category_revenue():
    cat_rev = od.groupby('categoryName')['revenue'].sum().sort_values(ascending=False)
    return jsonify({
        'labels': cat_rev.index.tolist(),
        'values': [round(v, 2) for v in cat_rev.tolist()]
    })


@app.route('/api/top-customers')
def top_customers():
    cust_rev = od.groupby('contactName')['revenue'].sum().sort_values(ascending=True).tail(10)
    return jsonify({
        'labels': cust_rev.index.tolist(),
        'values': [round(v, 2) for v in cust_rev.tolist()]
    })


@app.route('/api/employee-performance')
def employee_performance():
    emp_data = od.groupby('employeeName').agg(
        revenue=('revenue', 'sum'),
        orderCount=('orderID', 'nunique')
    ).sort_values('revenue', ascending=False).reset_index()

    return jsonify({
        'labels': emp_data['employeeName'].tolist(),
        'revenue': [round(v, 2) for v in emp_data['revenue'].tolist()],
        'orderCount': emp_data['orderCount'].tolist()
    })


@app.route('/api/delivery-status')
def delivery_status():
    shipped = orders.dropna(subset=['shippedDate'])
    on_time = int((shipped['shippedDate'] <= shipped['requiredDate']).sum())
    late = int((shipped['shippedDate'] > shipped['requiredDate']).sum())
    pending = int(orders['shippedDate'].isna().sum())

    return jsonify({
        'labels': ['On Time', 'Late', 'Pending'],
        'values': [on_time, late, pending],
        'colors': ['#22c55e', '#ef4444', '#f59e0b']
    })


@app.route('/api/shipper-performance')
def shipper_performance():
    shipped_with = orders.dropna(subset=['shippedDate']).merge(
        shippers[['shipperID', 'companyName']], left_on='shipVia', right_on='shipperID', how='left'
    )
    shipped_with['onTime'] = shipped_with['shippedDate'] <= shipped_with['requiredDate']

    stats = shipped_with.groupby('companyName').agg(
        orderCount=('orderID', 'count'),
        avgFreight=('freight', 'mean'),
        onTimeRate=('onTime', 'mean')
    ).reset_index()
    stats['onTimeRate'] = (stats['onTimeRate'] * 100).round(1)

    all_shippers = orders.merge(
        shippers[['shipperID', 'companyName']], left_on='shipVia', right_on='shipperID', how='left'
    ).groupby('companyName')['orderID'].count().reset_index()
    all_shippers.columns = ['companyName', 'totalOrders']

    stats = stats.merge(all_shippers, on='companyName', how='left')

    return jsonify({
        'labels': stats['companyName'].tolist(),
        'orderCount': stats['totalOrders'].tolist(),
        'avgFreight': [round(v, 2) for v in stats['avgFreight'].tolist()],
        'onTimeRate': stats['onTimeRate'].tolist()
    })


@app.route('/api/top-products')
def top_products():
    prod_rev = od.groupby('productName')['revenue'].sum().sort_values(ascending=True).tail(10)
    return jsonify({
        'labels': prod_rev.index.tolist(),
        'values': [round(v, 2) for v in prod_rev.tolist()]
    })


@app.route('/api/freight-trend')
def freight_trend():
    df = orders.copy()
    df['yearMonth'] = df['orderDate'].dt.to_period('M').astype(str)
    mf = df.groupby('yearMonth')['freight'].agg(['sum', 'mean']).reset_index()
    mf.columns = ['yearMonth', 'totalFreight', 'avgFreight']
    mf = mf.sort_values('yearMonth')

    return jsonify({
        'labels': mf['yearMonth'].tolist(),
        'totalFreight': [round(v, 2) for v in mf['totalFreight'].tolist()],
        'avgFreight': [round(v, 2) for v in mf['avgFreight'].tolist()]
    })


@app.route('/api/inventory')
def inventory():
    df = products[['productName', 'unitsInStock', 'unitsOnOrder', 'reorderLevel']].sort_values(
        'unitsInStock', ascending=False
    ).head(15)
    return jsonify({
        'labels': df['productName'].tolist(),
        'inStock': df['unitsInStock'].tolist(),
        'onOrder': df['unitsOnOrder'].tolist(),
        'reorderLevel': df['reorderLevel'].tolist()
    })


@app.route('/api/freight-by-country')
def freight_by_country():
    fc = orders.groupby('shipCountry').agg(
        totalFreight=('freight', 'sum'),
        orderCount=('orderID', 'count')
    ).sort_values('totalFreight', ascending=True).tail(15)

    return jsonify({
        'labels': fc.index.tolist(),
        'totalFreight': [round(v, 2) for v in fc['totalFreight'].tolist()],
        'orderCount': fc['orderCount'].tolist()
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
