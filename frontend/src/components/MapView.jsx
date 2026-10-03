import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const DISTRICT_COORDINATES = {
  Pune: [18.5204, 73.8567],
  Nagpur: [21.1458, 79.0882],
  'Bengaluru Urban': [12.9716, 77.5946],
  Mysuru: [12.2958, 76.6394],
  Chennai: [13.0827, 80.2707],
  Coimbatore: [11.0168, 76.9558],
  Hyderabad: [17.385, 78.4867],
  Warangal: [17.9689, 79.5941],
  Ahmedabad: [23.0225, 72.5714],
  Surat: [21.1702, 72.8311],
}

export default function MapView({ forecasts }) {
  const byDistrict = new Map()
  for (const row of forecasts) {
    const location = byDistrict.get(row.district) || {
      district: row.district,
      state: row.state,
      demand: 0,
      supply: 0,
    }
    location.demand += Number(row.forecast_demand) || 0
    location.supply += Number(row.forecast_supply) || 0
    byDistrict.set(row.district, location)
  }

  return (
    <MapContainer className="india-map" center={[21, 79]} zoom={4.5} scrollWheelZoom={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {[...byDistrict.values()].map((location) => {
        const coordinates = DISTRICT_COORDINATES[location.district]
        if (!coordinates) return null
        const gap = location.demand - location.supply
        return (
          <CircleMarker
            key={location.district}
            center={coordinates}
            radius={Math.min(15, 7 + Math.abs(gap) / Math.max(location.demand, 1) * 12)}
            pathOptions={{
              color: gap > 0 ? '#cf653e' : '#2d807b',
              fillColor: gap > 0 ? '#cf653e' : '#2d807b',
              fillOpacity: 0.78,
              weight: 1,
            }}
          >
            <Popup>
              <strong>{location.district}, {location.state}</strong>
              <br />Demand {Math.round(location.demand).toLocaleString('en-IN')}
              <br />Supply {Math.round(location.supply).toLocaleString('en-IN')}
              <br />Gap {Math.round(gap).toLocaleString('en-IN')}
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}