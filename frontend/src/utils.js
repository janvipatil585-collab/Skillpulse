export const numberFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
export const decimalFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })

export function formatNumber(value) {
  return numberFormat.format(Number(value) || 0)
}

export function formatDecimal(value) {
  return decimalFormat.format(Number(value) || 0)
}

export function formatDate(value, options = { month: 'short', year: 'numeric' }) {
  if (!value) return 'Not available'
  return new Intl.DateTimeFormat('en-IN', options).format(new Date(value))
}

export function buildMonthlySeries(rows) {
  const monthly = new Map()
  for (const row of rows) {
    const month = row.forecast_month
    const item = monthly.get(month) || { month, demand: 0, supply: 0 }
    item.demand += Number(row.forecast_demand) || 0
    item.supply += Number(row.forecast_supply) || 0
    monthly.set(month, item)
  }
  return [...monthly.values()].sort((a, b) => a.month.localeCompare(b.month))
}

export function buildGapSeries(rows, limit = 8) {
  const trades = new Map()
  for (const row of rows) {
    const item = trades.get(row.trade) || { trade: row.trade, shortage: 0, oversupply: 0 }
    if (Number(row.skill_gap) > 0) item.shortage += Number(row.skill_gap)
    else item.oversupply += Math.abs(Number(row.skill_gap))
    trades.set(row.trade, item)
  }
  return [...trades.values()]
    .sort((a, b) => b.shortage + b.oversupply - (a.shortage + a.oversupply))
    .slice(0, limit)
}

export function sortRows(rows, key, direction = 'desc') {
  const multiplier = direction === 'asc' ? 1 : -1
  return [...rows].sort((left, right) => {
    const a = left[key]
    const b = right[key]
    if (typeof a === 'number' && typeof b === 'number') return (a - b) * multiplier
    return String(a ?? '').localeCompare(String(b ?? '')) * multiplier
  })
}