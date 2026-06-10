'use strict';

const COLORS = ['#FF9900','#146EB4','#22c55e','#8b5cf6','#ef4444','#14b8a6','#f59e0b','#ec4899','#6366f1','#06b6d4','#84cc16','#f97316','#0ea5e9','#a855f7','#10b981'];
const PAGE_TITLES = { overview:'Overview', orders:'Orders', revenue:'Revenue', shipping:'Shipping Performance', products:'Products', team:'Team Performance' };

let charts = {};
let loaded = {};

function fmt(n, prefix='', suffix='') {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return prefix + (n/1_000_000).toFixed(1) + 'M' + suffix;
  if (n >= 1_000) return prefix + (n/1_000).toFixed(1) + 'K' + suffix;
  return prefix + n.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 1}) + suffix;
}

function animateValue(el, end, prefix='', suffix='') {
  const duration = 900;
  const start = 0;
  const startTime = performance.now();
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = start + (end - start) * ease;
    el.textContent = fmt(current, prefix, suffix);
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = fmt(end, prefix, suffix);
  }
  requestAnimationFrame(step);
}

function defaultOptions(extra={}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { font: { size: 12 }, color: '#64748b', boxWidth: 12, padding: 12 } },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f8fafc',
        bodyColor: '#cbd5e1',
        borderColor: '#334155',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
      },
    },
    ...extra
  };
}

function scaleOptions(extra={}) {
  return {
    x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } }, ...extra.x },
    y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } }, ...extra.y }
  };
}

async function api(endpoint) {
  const res = await fetch(endpoint);
  return res.json();
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

// ───────────── OVERVIEW ─────────────
async function loadOverview() {
  const [kpis, timeSeries, catRev, delStatus, topCust] = await Promise.all([
    api('/api/kpis'),
    api('/api/orders-over-time'),
    api('/api/category-revenue'),
    api('/api/delivery-status'),
    api('/api/top-customers')
  ]);

  animateValue(document.getElementById('kpi-totalOrders'), kpis.totalOrders);
  animateValue(document.getElementById('kpi-totalRevenue'), kpis.totalRevenue, '$');
  animateValue(document.getElementById('kpi-onTimeRate'), kpis.onTimeRate, '', '%');
  animateValue(document.getElementById('kpi-totalCustomers'), kpis.totalCustomers);
  animateValue(document.getElementById('kpi-avgFreight'), kpis.avgFreight, '$');
  animateValue(document.getElementById('kpi-avgOrderValue'), kpis.avgOrderValue, '$');

  // Orders & Revenue dual-axis
  destroyChart('ordersRevenueChart');
  charts['ordersRevenueChart'] = new Chart(document.getElementById('ordersRevenueChart'), {
    type: 'line',
    data: {
      labels: timeSeries.labels,
      datasets: [
        {
          label: 'Revenue ($)',
          data: timeSeries.revenue,
          borderColor: '#FF9900',
          backgroundColor: 'rgba(255,153,0,.1)',
          fill: true,
          tension: 0.4,
          yAxisID: 'y',
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: 'Orders',
          data: timeSeries.orderCount,
          borderColor: '#146EB4',
          backgroundColor: 'transparent',
          tension: 0.4,
          yAxisID: 'y1',
          borderDash: [5,3],
          pointRadius: 3,
          pointHoverRadius: 6,
        }
      ]
    },
    options: {
      ...defaultOptions(),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } } },
        y: { position: 'left', grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      }
    }
  });

  // Category donut
  destroyChart('categoryDonutChart');
  charts['categoryDonutChart'] = new Chart(document.getElementById('categoryDonutChart'), {
    type: 'doughnut',
    data: {
      labels: catRev.labels,
      datasets: [{ data: catRev.values, backgroundColor: COLORS, borderWidth: 2, borderColor: '#fff' }]
    },
    options: { ...defaultOptions({ cutout: '60%' }) }
  });

  // Delivery donut
  destroyChart('deliveryDonutChart');
  charts['deliveryDonutChart'] = new Chart(document.getElementById('deliveryDonutChart'), {
    type: 'doughnut',
    data: {
      labels: delStatus.labels,
      datasets: [{ data: delStatus.values, backgroundColor: delStatus.colors, borderWidth: 2, borderColor: '#fff' }]
    },
    options: { ...defaultOptions({ cutout: '60%' }) }
  });

  // Top customers horizontal bar
  destroyChart('topCustomersOverviewChart');
  charts['topCustomersOverviewChart'] = new Chart(document.getElementById('topCustomersOverviewChart'), {
    type: 'bar',
    data: {
      labels: topCust.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: topCust.values,
        backgroundColor: COLORS.slice(0, topCust.labels.length),
        borderRadius: 6,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 12 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });
}

// ───────────── ORDERS ─────────────
async function loadOrders() {
  const [timeSeries, byCountry, shipPerf, freightTrend] = await Promise.all([
    api('/api/orders-over-time'),
    api('/api/freight-by-country'),
    api('/api/shipper-performance'),
    api('/api/freight-trend')
  ]);

  destroyChart('monthlyOrdersChart');
  charts['monthlyOrdersChart'] = new Chart(document.getElementById('monthlyOrdersChart'), {
    type: 'bar',
    data: {
      labels: timeSeries.labels,
      datasets: [{
        label: 'Orders',
        data: timeSeries.orderCount,
        backgroundColor: 'rgba(255,153,0,.8)',
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions(),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('ordersByCountryChart');
  charts['ordersByCountryChart'] = new Chart(document.getElementById('ordersByCountryChart'), {
    type: 'bar',
    data: {
      labels: byCountry.labels,
      datasets: [{
        label: 'Orders',
        data: byCountry.orderCount,
        backgroundColor: 'rgba(20,110,180,.8)',
        borderRadius: 5,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('ordersByShipperChart');
  charts['ordersByShipperChart'] = new Chart(document.getElementById('ordersByShipperChart'), {
    type: 'bar',
    data: {
      labels: shipPerf.labels,
      datasets: [{
        label: 'Total Orders',
        data: shipPerf.orderCount,
        backgroundColor: COLORS.slice(0, 3),
        borderRadius: 8,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions(),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('freightTrendChart');
  charts['freightTrendChart'] = new Chart(document.getElementById('freightTrendChart'), {
    type: 'line',
    data: {
      labels: freightTrend.labels,
      datasets: [{
        label: 'Total Freight ($)',
        data: freightTrend.totalFreight,
        borderColor: '#14b8a6',
        backgroundColor: 'rgba(20,184,166,.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } } },
        y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });
}

// ───────────── REVENUE ─────────────
async function loadRevenue() {
  const [timeSeries, byCountry, byCat, topCust] = await Promise.all([
    api('/api/orders-over-time'),
    api('/api/revenue-by-country'),
    api('/api/category-revenue'),
    api('/api/top-customers')
  ]);

  destroyChart('revenueAreaChart');
  charts['revenueAreaChart'] = new Chart(document.getElementById('revenueAreaChart'), {
    type: 'line',
    data: {
      labels: timeSeries.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: timeSeries.revenue,
        borderColor: '#FF9900',
        backgroundColor: 'rgba(255,153,0,.15)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 7,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 } } },
        y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('revenueByCountryChart');
  charts['revenueByCountryChart'] = new Chart(document.getElementById('revenueByCountryChart'), {
    type: 'bar',
    data: {
      labels: byCountry.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: byCountry.values,
        backgroundColor: 'rgba(255,153,0,.85)',
        borderRadius: 5,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('revenueByCategoryChart');
  charts['revenueByCategoryChart'] = new Chart(document.getElementById('revenueByCategoryChart'), {
    type: 'bar',
    data: {
      labels: byCat.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: byCat.values,
        backgroundColor: COLORS.slice(0, byCat.labels.length),
        borderRadius: 6,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions({ y: { ticks: { callback: v => '$' + fmt(v) } } }),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('topCustomersChart');
  charts['topCustomersChart'] = new Chart(document.getElementById('topCustomersChart'), {
    type: 'bar',
    data: {
      labels: topCust.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: topCust.values,
        backgroundColor: 'rgba(139,92,246,.8)',
        borderRadius: 5,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });
}

// ───────────── SHIPPING ─────────────
async function loadShipping() {
  const [delStatus, shipPerf, freightCountry] = await Promise.all([
    api('/api/delivery-status'),
    api('/api/shipper-performance'),
    api('/api/freight-by-country')
  ]);

  destroyChart('deliveryLargeChart');
  charts['deliveryLargeChart'] = new Chart(document.getElementById('deliveryLargeChart'), {
    type: 'doughnut',
    data: {
      labels: delStatus.labels,
      datasets: [{ data: delStatus.values, backgroundColor: delStatus.colors, borderWidth: 3, borderColor: '#fff' }]
    },
    options: { ...defaultOptions({ cutout: '65%' }) }
  });

  destroyChart('shipperOnTimeChart');
  charts['shipperOnTimeChart'] = new Chart(document.getElementById('shipperOnTimeChart'), {
    type: 'bar',
    data: {
      labels: shipPerf.labels,
      datasets: [{
        label: 'On-Time Rate (%)',
        data: shipPerf.onTimeRate,
        backgroundColor: ['#22c55e','#14b8a6','#3b82f6'],
        borderRadius: 8,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions({ y: { ticks: { callback: v => v + '%' }, suggestedMax: 100 } }),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('shipperComparisonChart');
  charts['shipperComparisonChart'] = new Chart(document.getElementById('shipperComparisonChart'), {
    type: 'bar',
    data: {
      labels: shipPerf.labels,
      datasets: [
        {
          label: 'Total Orders',
          data: shipPerf.orderCount,
          backgroundColor: 'rgba(255,153,0,.85)',
          borderRadius: 5,
          yAxisID: 'y',
        },
        {
          label: 'Avg Freight ($)',
          data: shipPerf.avgFreight,
          backgroundColor: 'rgba(20,110,180,.75)',
          borderRadius: 5,
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      ...defaultOptions(),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        y: { position: 'left', grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#64748b', callback: v => '$' + v } }
      }
    }
  });

  destroyChart('freightByCountryChart');
  charts['freightByCountryChart'] = new Chart(document.getElementById('freightByCountryChart'), {
    type: 'bar',
    data: {
      labels: freightCountry.labels,
      datasets: [{
        label: 'Total Freight ($)',
        data: freightCountry.totalFreight,
        backgroundColor: 'rgba(20,184,166,.8)',
        borderRadius: 5,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });
}

// ───────────── PRODUCTS ─────────────
async function loadProducts() {
  const [topProds, catRev, inv] = await Promise.all([
    api('/api/top-products'),
    api('/api/category-revenue'),
    api('/api/inventory')
  ]);

  destroyChart('topProductsChart');
  charts['topProductsChart'] = new Chart(document.getElementById('topProductsChart'), {
    type: 'bar',
    data: {
      labels: topProds.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: topProds.values,
        backgroundColor: 'rgba(255,153,0,.85)',
        borderRadius: 5,
      }]
    },
    options: {
      ...defaultOptions({ indexAxis: 'y' }),
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + fmt(v) } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
      },
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('categoryBarChart');
  charts['categoryBarChart'] = new Chart(document.getElementById('categoryBarChart'), {
    type: 'bar',
    data: {
      labels: catRev.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: catRev.values,
        backgroundColor: COLORS.slice(0, catRev.labels.length),
        borderRadius: 6,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions({ y: { ticks: { callback: v => '$' + fmt(v) } } }),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('inventoryChart');
  charts['inventoryChart'] = new Chart(document.getElementById('inventoryChart'), {
    type: 'bar',
    data: {
      labels: inv.labels,
      datasets: [
        { label: 'In Stock', data: inv.inStock, backgroundColor: 'rgba(34,197,94,.8)', borderRadius: 4 },
        { label: 'On Order', data: inv.onOrder, backgroundColor: 'rgba(59,130,246,.8)', borderRadius: 4 },
      ]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions(),
    }
  });
}

// ───────────── TEAM ─────────────
async function loadTeam() {
  const empData = await api('/api/employee-performance');

  destroyChart('employeeRevenueChart');
  charts['employeeRevenueChart'] = new Chart(document.getElementById('employeeRevenueChart'), {
    type: 'bar',
    data: {
      labels: empData.labels,
      datasets: [{
        label: 'Revenue ($)',
        data: empData.revenue,
        backgroundColor: COLORS.slice(0, empData.labels.length),
        borderRadius: 8,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions({ y: { ticks: { callback: v => '$' + fmt(v) } } }),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });

  destroyChart('employeeOrdersChart');
  charts['employeeOrdersChart'] = new Chart(document.getElementById('employeeOrdersChart'), {
    type: 'bar',
    data: {
      labels: empData.labels,
      datasets: [{
        label: 'Orders Handled',
        data: empData.orderCount,
        backgroundColor: 'rgba(255,153,0,.8)',
        borderRadius: 8,
      }]
    },
    options: {
      ...defaultOptions(),
      scales: scaleOptions(),
      plugins: { ...defaultOptions().plugins, legend: { display: false } }
    }
  });
}

// ───────────── NAVIGATION ─────────────
const loaders = { overview: loadOverview, orders: loadOrders, revenue: loadRevenue, shipping: loadShipping, products: loadProducts, team: loadTeam };

function navigate(page) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === page + '-page'));
  document.getElementById('pageTitle').textContent = PAGE_TITLES[page] || page;

  if (!loaded[page]) {
    loaded[page] = true;
    loaders[page]();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  document.getElementById('menuBtn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('collapsed');
  });

  navigate('overview');
});
