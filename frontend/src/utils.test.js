import { describe, expect, it } from 'vitest'

import { buildQuery } from './api/client'
import { buildGapSeries, buildMonthlySeries, sortRows } from './utils'

describe('dashboard data helpers', () => {
  it('serializes only selected filters for real API requests', () => {
    expect(buildQuery({ state: 'KA', district: '', horizon: 6 })).toBe('state=KA&horizon=6')
  })

  it('aggregates month and skill-gap chart values from fetched records', () => {
    const records = [
      { forecast_month: '2026-10-01', forecast_demand: 10, forecast_supply: 8, skill_gap: 2, trade: 'Solar' },
      { forecast_month: '2026-10-01', forecast_demand: 20, forecast_supply: 21, skill_gap: -1, trade: 'Solar' },
      { forecast_month: '2026-11-01', forecast_demand: 5, forecast_supply: 5, skill_gap: 0, trade: 'Solar' },
    ]

    expect(buildMonthlySeries(records)).toEqual([
      { month: '2026-10-01', demand: 30, supply: 29 },
      { month: '2026-11-01', demand: 5, supply: 5 },
    ])
    expect(buildGapSeries(records)).toEqual([{ trade: 'Solar', shortage: 2, oversupply: 1 }])
  })

  it('sorts tabular records by a selected column', () => {
    expect(sortRows([{ gap: 2 }, { gap: -3 }], 'gap', 'asc').map((row) => row.gap)).toEqual([-3, 2])
  })
})