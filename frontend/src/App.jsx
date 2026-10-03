import { useEffect, useState } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight, BarChart3, BrainCircuit, Boxes, ChevronDown, Database, FileUp, Gauge, MapPin, RefreshCw, SlidersHorizontal, Sparkles, Users } from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'

import { apiGet, API_BASE_URL } from './api/client'
import MapView from './components/MapView'
import { buildGapSeries, buildMonthlySeries, formatDate, formatDecimal, formatNumber, sortRows } from './utils'

const NAV = [
  { label: 'Dashboard', path: '/dashboard', icon: Gauge },
  { label: 'Forecast', path: '/forecast', icon: Activity },
  { label: 'Skill gaps', path: '/skill-gaps', icon: BarChart3 },
  { label: 'Recommendations', path: '/recommendations', icon: Sparkles },
  { label: 'Data', path: '/data', icon: Database },
  { label: 'Model', path: '/model', icon: BrainCircuit },
]
const TITLES = Object.fromEntries(NAV.map(({ label, path }) => [path, label]))
const EMPTY = { summary: null, forecasts: [], gaps: [], recommendations: [], metrics: [], database: null }

function Pill({ status }) {
  return <span className={`status-pill status-${status}`}>{status}</span>
}

function SectionTitle({ title, detail, action }) {
  return <div className="section-title"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{action}</div>
}

function MetricCard({ label, value, detail, icon: Icon, tone }) {
  return <article className={`metric-card metric-${tone}`}><div className="metric-topline"><span>{label}</span><Icon size={17} /></div><strong>{value}</strong><small>{detail}</small></article>
}

function FilterBar({ filters, setFilters, options, loading }) {
  const change = (key, value) => setFilters((current) => ({
    ...current,
    [key]: value,
    ...(key === 'state' ? { district: '', trade: '' } : {}),
    ...(key === 'sector' ? { trade: '' } : {}),
  }))
  const select = (label, key, items, getValue, getLabel, getKey = getValue) => (
    <label className={`filter-select ${key === 'trade' ? 'trade-filter' : ''}`} key={key}>
      <span>{label}</span>
      <select value={filters[key]} onChange={(event) => change(key, event.target.value)}>
        <option value="">All {label.toLowerCase()}s</option>
        {items.map((item) => <option key={getKey(item)} value={getValue(item)}>{getLabel(item)}</option>)}
      </select><ChevronDown size={14} aria-hidden="true" />
    </label>
  )

  return (
    <section className="filter-bar" aria-label="Dashboard filters">
      <div className="filter-label"><SlidersHorizontal size={16} /><span>Refine view</span></div>
      {select('State', 'state', options.states, (item) => item.code, (item) => item.name)}
      {select('District', 'district', options.districts, (item) => item.name, (item) => item.name, (item) => `${item.code}-${item.name}`)}
      {select('Sector', 'sector', options.sectors, (item) => item, (item) => item)}
      {select('Trade', 'trade', options.trades, (item) => item.name, (item) => item.name, (item) => `${item.sector}-${item.name}`)}
      <div className="horizon-filter"><span>Horizon</span><div className="segmented-control" role="group" aria-label="Forecast horizon">
        {[3, 6, 12].map((value) => <button aria-pressed={Number(filters.horizon) === value} className={Number(filters.horizon) === value ? 'selected' : ''} key={value} onClick={() => change('horizon', value)} type="button">{value}m</button>)}
      </div></div>
      <span className={`filter-sync ${loading ? 'syncing' : ''}`} title={loading ? 'Refreshing from API' : 'Data is current'}><RefreshCw size={15} /></span>
    </section>
  )
}

function DashboardPage({ data, horizon }) {
  const monthly = buildMonthlySeries(data.forecasts)
  const gaps = buildGapSeries(data.forecasts)
  const districtRows = [...new Map(data.forecasts.map((row) => [row.district, row])).values()]
  const summary = data.summary || {}
  return <>
    <section className="metric-grid">
      <MetricCard label="Labour demand" value={formatNumber(summary.total_labour_demand)} detail={`Forecast window · ${horizon} months`} tone="green" icon={Users} />
      <MetricCard label="Training supply" value={formatNumber(summary.total_labour_supply)} detail="Available trainees" tone="blue" icon={Boxes} />
      <MetricCard label="Shortage gap" value={formatNumber(summary.total_skill_gap)} detail="Positive demand less supply" tone="amber" icon={ArrowUpRight} />
      <MetricCard label="Shortage series" value={formatNumber(summary.shortage_count)} detail="District · trade · month" tone="coral" icon={ArrowUpRight} />
      <MetricCard label="Oversupply series" value={formatNumber(summary.oversupply_count)} detail="District · trade · month" tone="slate" icon={ArrowDownRight} />
    </section>
    <div className="dashboard-grid dashboard-main-grid">
      <section className="panel chart-panel"><SectionTitle title="Demand and training supply" detail="Monthly totals from persisted model forecasts" />
        {monthly.length ? <div className="chart-wrap chart-tall"><ResponsiveContainer width="100%" height="100%"><AreaChart data={monthly} margin={{ top: 16, right: 12, left: 2, bottom: 0 }}>
          <defs><linearGradient id="demandFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#2e7872" stopOpacity={0.2} /><stop offset="100%" stopColor="#2e7872" stopOpacity={0} /></linearGradient><linearGradient id="supplyFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#d7a85e" stopOpacity={0.2} /><stop offset="100%" stopColor="#d7a85e" stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid vertical={false} stroke="#e9ece7" /><XAxis dataKey="month" tickFormatter={(value) => formatDate(value)} tickLine={false} axisLine={false} minTickGap={24} /><YAxis tickFormatter={(value) => `${Math.round(value / 1000)}k`} tickLine={false} axisLine={false} width={44} />
          <Tooltip labelFormatter={(value) => formatDate(value, { month: 'long', year: 'numeric' })} formatter={(value) => formatNumber(value)} /><Legend verticalAlign="top" align="right" height={32} />
          <Area type="monotone" dataKey="demand" name="Demand" stroke="#2e7872" fill="url(#demandFill)" strokeWidth={2.5} /><Area type="monotone" dataKey="supply" name="Training supply" stroke="#d7a85e" fill="url(#supplyFill)" strokeWidth={2.5} />
        </AreaChart></ResponsiveContainer></div> : <EmptyState message="No persisted forecasts for this filter yet." />}
      </section>
      <section className="panel map-panel"><SectionTitle title="Regional outlook" detail="Forecast pressure by district" action={<span className="map-key"><i /> Shortage</span>} />
        {data.forecasts.length ? <MapView forecasts={data.forecasts} /> : <EmptyState message="Forecasts will appear on the map after training." />}
        <div className="map-footer"><MapPin size={14} /> {districtRows.length} districts in selected view</div>
      </section>
    </div>
    <div className="dashboard-grid dashboard-bottom-grid">
      <section className="panel"><SectionTitle title="Largest trade gaps" detail="Forecast pressure by trade" action={<Link className="text-link" to="/skill-gaps">View all</Link>} />
        {gaps.length ? <div className="chart-wrap chart-short"><ResponsiveContainer width="100%" height="100%"><BarChart data={gaps} layout="vertical" margin={{ left: 8, right: 12, top: 2, bottom: 2 }}>
          <CartesianGrid horizontal={false} stroke="#e9ece7" /><XAxis type="number" tickLine={false} axisLine={false} /><YAxis type="category" dataKey="trade" width={150} tickLine={false} axisLine={false} /><Tooltip formatter={(value) => formatNumber(value)} /><Legend />
          <Bar dataKey="shortage" name="Shortage" fill="#cf653e" radius={[0, 3, 3, 0]} /><Bar dataKey="oversupply" name="Oversupply" fill="#4a9690" radius={[0, 3, 3, 0]} />
        </BarChart></ResponsiveContainer></div> : <EmptyState message="No skill-gap results for this selection." />}
      </section>
      <section className="panel"><SectionTitle title="District snapshot" detail="Latest forecast month by location" /><div className="compact-list">
        {districtRows.slice(0, 7).map((row) => <div className="compact-row" key={row.district}><div className="compact-location"><MapPin size={14} /><span>{row.district}</span><small>{row.state}</small></div><Pill status={row.classification} /><strong>{formatNumber(row.skill_gap)}</strong></div>)}
        {!districtRows.length && <EmptyState message="No district forecasts available." />}
      </div></section>
    </div>
  </>
}

function ForecastTable({ rows }) {
  return <div className="table-scroll"><table><thead><tr><th>Forecast month</th><th>State / district</th><th>Sector / trade</th><th>Demand</th><th>Supply</th><th>Gap</th><th>Status</th></tr></thead><tbody>
    {rows.map((row) => <tr key={row.id}><td>{formatDate(row.forecast_month, { month: 'short', year: 'numeric' })}</td><td><strong>{row.district}</strong><small className="cell-secondary">{row.state}</small></td><td><strong>{row.trade}</strong><small className="cell-secondary">{row.sector}</small></td><td>{formatDecimal(row.forecast_demand)}</td><td>{formatDecimal(row.forecast_supply)}</td><td className={Number(row.skill_gap) > 0 ? 'gap-positive' : 'gap-negative'}>{formatDecimal(row.skill_gap)}</td><td><Pill status={row.classification} /></td></tr>)}
  </tbody></table>{!rows.length && <EmptyState message="No forecast rows for these filters." />}</div>
}

function ForecastPage({ data }) {
  const monthly = buildMonthlySeries(data.forecasts)
  return <>
    <section className="panel"><SectionTitle title="Monthly forecast trajectory" detail={`${data.forecasts.length.toLocaleString('en-IN')} stored district-trade months · from PostgreSQL`} />
      {monthly.length ? <div className="chart-wrap forecast-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={monthly} margin={{ top: 14, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#e9ece7" /><XAxis dataKey="month" tickFormatter={(value) => formatDate(value)} tickLine={false} axisLine={false} /><YAxis tickFormatter={(value) => `${Math.round(value / 1000)}k`} tickLine={false} axisLine={false} />
        <Tooltip labelFormatter={(value) => formatDate(value, { month: 'long', year: 'numeric' })} formatter={(value) => formatNumber(value)} /><Legend /><Area type="monotone" dataKey="demand" name="Forecast demand" stroke="#2e7872" fill="#2e7872" fillOpacity={0.12} strokeWidth={2.5} /><Area type="monotone" dataKey="supply" name="Forecast supply" stroke="#d7a85e" fill="#d7a85e" fillOpacity={0.12} strokeWidth={2.5} />
      </AreaChart></ResponsiveContainer></div> : <EmptyState message="No forecast rows are stored for this horizon." />}
    </section>
    <section className="panel table-panel"><SectionTitle title="Forecast records" detail="Model outputs by month, location and trade" /><ForecastTable rows={data.forecasts.slice(0, 100)} />{data.forecasts.length > 100 && <p className="table-note">Showing 100 of {data.forecasts.length.toLocaleString('en-IN')} rows.</p>}</section>
  </>
}

function SkillGapsPage({ rows }) {
  const [sort, setSort] = useState({ key: 'skill_gap', direction: 'desc' })
  const [search, setSearch] = useState('')
  const filtered = rows.filter((row) => `${row.state} ${row.district} ${row.sector} ${row.trade}`.toLowerCase().includes(search.toLowerCase()))
  const sorted = sortRows(filtered, sort.key, sort.direction)
  const changeSort = (key) => setSort((current) => ({ key, direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc' }))
  const heading = (label, key) => <button className="sort-button" onClick={() => changeSort(key)} type="button">{label}<span aria-hidden="true">↕</span></button>
  return <section className="panel table-panel"><SectionTitle title="Skill gap register" detail={`${filtered.length.toLocaleString('en-IN')} forecast-month records · select a heading to sort`} action={<label className="search-box"><span className="sr-only">Search skill gaps</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search trade or district" /></label>} />
    <div className="table-scroll"><table><thead><tr><th>{heading('State', 'state')}</th><th>{heading('District', 'district')}</th><th>{heading('Sector', 'sector')}</th><th>{heading('Trade', 'trade')}</th><th>{heading('Demand', 'forecast_demand')}</th><th>{heading('Supply', 'forecast_supply')}</th><th>{heading('Skill gap', 'skill_gap')}</th><th>{heading('Status', 'classification')}</th></tr></thead><tbody>
      {sorted.slice(0, 250).map((row) => <tr key={row.id}><td>{row.state}</td><td>{row.district}</td><td>{row.sector}</td><td><strong>{row.trade}</strong></td><td>{formatDecimal(row.forecast_demand)}</td><td>{formatDecimal(row.forecast_supply)}</td><td className={Number(row.skill_gap) > 0 ? 'gap-positive' : 'gap-negative'}>{formatDecimal(row.skill_gap)}</td><td><Pill status={row.classification} /></td></tr>)}
    </tbody></table>{!sorted.length && <EmptyState message="No skill gaps match these filters." />}{sorted.length > 250 && <p className="table-note">Showing the first 250 of {sorted.length.toLocaleString('en-IN')} matching rows.</p>}</div>
  </section>
}

function RecommendationsPage({ rows }) {
  return <section className="panel table-panel"><SectionTitle title="Training capacity actions" detail="Recommendations use forecast gaps and current PostgreSQL training capacity" />
    <div className="table-scroll"><table><thead><tr><th>Priority</th><th>Trade</th><th>Location</th><th>Forecast month</th><th>Skill gap</th><th>Additional capacity</th><th>Reason</th></tr></thead><tbody>
      {rows.slice(0, 250).map((row) => <tr key={row.id}><td><span className={`priority priority-${row.priority}`}>{row.priority}</span></td><td><strong>{row.trade}</strong><small className="cell-secondary">{row.sector}</small></td><td>{row.district}<small className="cell-secondary">{row.state}</small></td><td>{formatDate(row.forecast_month, { month: 'short', year: 'numeric' })}</td><td className="gap-positive">{formatDecimal(row.skill_gap)}</td><td><strong>{formatNumber(row.recommended_additional_capacity)}</strong><small className="cell-secondary">Capacity {formatNumber(row.current_training_capacity)}</small></td><td className="reason-cell">{row.reason}</td></tr>)}
    </tbody></table>{!rows.length && <EmptyState message="No shortage recommendations for the current selection." />}{rows.length > 250 && <p className="table-note">Showing the first 250 of {rows.length.toLocaleString('en-IN')} recommendations.</p>}</div>
  </section>
}

function DataPage({ data }) {
  const summary = data.database
  const cards = [['States', summary?.states], ['Districts', summary?.districts], ['Sectors', summary?.sectors], ['Trades', summary?.trades], ['Historical months', summary?.historical_months], ['Demand records', summary?.demand_records], ['Training supply records', summary?.supply_records], ['Forecast records', summary?.forecast_records]]
  return <><section className="data-stat-grid">{cards.map(([label, value]) => <article className="data-stat" key={label}><span>{label}</span><strong>{value === undefined ? '—' : formatNumber(value)}</strong></article>)}</section>
    <section className="panel data-range-panel"><div className="data-range-icon"><Database size={21} /></div><div><span>Historical period</span><strong>{summary?.date_range?.start ? `${formatDate(summary.date_range.start)} — ${formatDate(summary.date_range.end)}` : 'No historical records'}</strong><small>Statistics are queried from PostgreSQL and reflect the selected dimensions.</small></div></section></>
}

function MetricGroup({ title, metric }) {
  return <section className="panel evaluation-panel"><SectionTitle title={title} detail={metric ? `${metric.forecast_horizon}-month chronological validation` : 'No evaluation record for this horizon'} /><div className="evaluation-values">
    {['mae', 'rmse', 'mape'].map((key) => <div key={key}><span>{key.toUpperCase()}</span><strong>{metric ? `${formatDecimal(metric[key])}${key === 'mape' ? '%' : ''}` : '—'}</strong></div>)}
  </div></section>
}

function ModelPage({ metrics, horizon }) {
  const selected = metrics.filter((item) => item.forecast_horizon === Number(horizon))
  const demand = selected.find((item) => item.target === 'demand')
  const supply = selected.find((item) => item.target === 'supply')
  const model = demand || supply || metrics[0]
  const horizons = [...new Set(metrics.map((item) => item.forecast_horizon))].sort((a, b) => a - b)
  return <>
    <section className="model-summary panel"><div className="model-icon"><BrainCircuit size={22} /></div><div className="model-title"><span>Forecasting model</span><h2>{model?.model_name || 'No trained model stored'}</h2><p>Real XGBoost regression · metrics shown are chronological holdout evaluation results</p></div><span className="model-version">{model?.model_version || 'Awaiting training'}</span></section>
    <section className="model-metric-grid"><MetricGroup title="Demand evaluation" metric={demand} /><MetricGroup title="Supply evaluation" metric={supply} /></section>
    <section className="panel model-details"><SectionTitle title="Training record" detail="Metadata read from model_metrics in PostgreSQL" /><dl className="details-grid">
      <div><dt>Training period</dt><dd>{model ? `${formatDate(model.training_start_date)} — ${formatDate(model.training_end_date)}` : 'Not available'}</dd></div>
      <div><dt>Last training time</dt><dd>{model ? formatDate(model.trained_at, { dateStyle: 'medium', timeStyle: 'short' }) : 'Not available'}</dd></div>
      <div><dt>Forecast horizons</dt><dd>{horizons.map((value) => `${value} months`).join(' · ') || 'Not available'}</dd></div>
      <div><dt>Feature count</dt><dd>{model?.feature_count ?? 'Not available'} encoded model columns</dd></div>
      <div><dt>Training rows</dt><dd>{model ? formatNumber(model.training_rows) : 'Not available'}</dd></div>
      <div><dt>Validation rows</dt><dd>{model ? formatNumber(model.validation_rows) : 'Not available'}</dd></div>
    </dl>{model?.model_config && <details className="config-details"><summary>Deterministic XGBoost configuration</summary><pre>{JSON.stringify(model.model_config, null, 2)}</pre></details>}</section>
    <section className="panel metrics-history"><SectionTitle title="Evaluation by horizon" detail="Demand and supply validation scores persisted for every horizon" /><div className="table-scroll"><table><thead><tr><th>Horizon</th><th>Target</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>Training period</th></tr></thead><tbody>
      {metrics.map((item) => <tr key={`${item.model_version}-${item.target}-${item.forecast_horizon}`}><td>{item.forecast_horizon} months</td><td className="capitalize">{item.target}</td><td>{formatDecimal(item.mae)}</td><td>{formatDecimal(item.rmse)}</td><td>{formatDecimal(item.mape)}%</td><td>{formatDate(item.training_start_date)} — {formatDate(item.training_end_date)}</td></tr>)}
    </tbody></table>{!metrics.length && <EmptyState message="No model evaluation records have been stored yet." />}</div></section>
  </>
}

function EmptyState({ message }) {
  return <div className="empty-state"><span><FileUp size={18} /></span><p>{message}</p></div>
}

function AppFrame() {
  const location = useLocation()
  const path = NAV.find((item) => item.path === location.pathname)?.path || '/dashboard'
  const [filters, setFilters] = useState({ state: '', district: '', sector: '', trade: '', horizon: 3 })
  const [options, setOptions] = useState({ states: [], districts: [], sectors: [], trades: [] })
  const [data, setData] = useState(EMPTY)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const updateFilters = (updater) => {
    setLoading(true)
    setFilters(updater)
  }

  useEffect(() => {
    const controller = new AbortController()
    apiGet('/api/filters', { state: filters.state, sector: filters.sector }, { signal: controller.signal })
      .then(setOptions).catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message) })
    return () => controller.abort()
  }, [filters.state, filters.sector])

  useEffect(() => {
    const controller = new AbortController()
    const dimensions = { state: filters.state, district: filters.district, sector: filters.sector, trade: filters.trade }
    const selected = { ...dimensions, horizon: filters.horizon }
    Promise.all([
      apiGet('/api/dashboard/summary', selected, { signal: controller.signal }),
      apiGet('/api/forecasts', selected, { signal: controller.signal }),
      apiGet('/api/skill-gaps', selected, { signal: controller.signal }),
      apiGet('/api/recommendations', selected, { signal: controller.signal }),
      apiGet('/api/model/metrics', {}, { signal: controller.signal }),
      apiGet('/api/data/summary', dimensions, { signal: controller.signal }),
    ]).then(([summary, forecasts, gaps, recommendations, metrics, database]) => {
      setData({ summary, forecasts: forecasts.items, gaps: gaps.items, recommendations: recommendations.items, metrics: metrics.items, database })
      setError('')
    }).catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [filters.state, filters.district, filters.sector, filters.trade, filters.horizon])

  return <div className="app-shell">
    <aside className="sidebar"><Link to="/dashboard" className="brand-lockup" aria-label="SkillPulse dashboard"><span className="brand-mark"><Activity size={19} /></span><span><strong>skillpulse</strong><small>LABOUR INTELLIGENCE</small></span></Link>
      <div className="workspace-label">WORKSPACE</div><nav className="primary-nav" aria-label="Main navigation">
        {NAV.map(({ label, path: target, icon: Icon }) => <NavLink className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} key={target} to={target}><Icon size={18} /><span>{label}</span>{target === '/recommendations' && data.recommendations.length > 0 && <small>{data.recommendations.length}</small>}</NavLink>)}
      </nav><div className="sidebar-spacer" /><div className="sidebar-source"><span className="source-light" /><div><strong>PostgreSQL connected</strong><small>Forecasts from XGBoost</small></div></div><div className="sidebar-foot">SKILLPULSE · SIH 2026</div>
    </aside>
    <main className="main-area"><header className="topbar"><div className="breadcrumb">Intelligence <span>/</span> {TITLES[path]}</div><div className="topbar-right"><span className={`live-indicator ${loading ? 'is-loading' : ''}`}><i />{loading ? 'Syncing data' : 'Live data'}</span><span className="topbar-date">India · {new Intl.DateTimeFormat('en-IN', { month: 'short', year: 'numeric' }).format(new Date())}</span></div></header>
      <div className="content-area"><div className="page-intro"><div><p className="eyebrow">LABOUR MARKET INTELLIGENCE</p><h1>{TITLES[path]}</h1><p className="page-description">Demand, training supply and skill signals across selected regions.</p></div><span className="model-chip"><span /> XGBoost · {data.metrics[0]?.model_version || 'model pending'}</span></div>
        <FilterBar filters={filters} setFilters={updateFilters} options={options} loading={loading} />
        {error && <div className="api-error" role="alert"><Database size={18} /><div><strong>Could not load live SkillPulse data</strong><span>{error} · API: {API_BASE_URL}</span></div><a href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">Open API docs</a></div>}
        <div className="page-content"><Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage data={data} horizon={filters.horizon} />} />
          <Route path="/forecast" element={<ForecastPage data={data} />} />
          <Route path="/skill-gaps" element={<SkillGapsPage rows={data.gaps} />} />
          <Route path="/recommendations" element={<RecommendationsPage rows={data.recommendations} />} />
          <Route path="/data" element={<DataPage data={data} />} />
          <Route path="/model" element={<ModelPage metrics={data.metrics} horizon={filters.horizon} />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes></div>
        <footer className="content-footer"><span>SkillPulse</span><span>PostgreSQL → FastAPI → XGBoost</span><span>{data.forecasts.length ? `${data.forecasts.length.toLocaleString('en-IN')} forecast rows loaded` : 'Waiting for persisted forecast data'}</span></footer>
      </div>
    </main>
  </div>
}

export default function App() {
  return <BrowserRouter><AppFrame /></BrowserRouter>
}
