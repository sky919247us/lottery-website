/**
 * 經銷商位置選擇器元件
 * 提供地圖，允許管理員透過點擊或拖拽標記來調整店家座標
 */
import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { Box, Typography, TextField } from '@mui/material'

// 修正 Leaflet 預設 Icon 路徑問題
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

interface LocationPickerProps {
  lat: number | null
  lng: number | null
  onChange: (lat: number, lng: number) => void
  initialCenter?: [number, number]
}

/** 地圖事件監聽器：處理點擊地圖更換位置 */
function MapClickHandler({ onLocationSelect }: { onLocationSelect: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng.lat, e.latlng.lng)
    },
  })
  return null
}

export default function RetailerLocationPicker({ lat, lng, onChange, initialCenter }: LocationPickerProps) {
  const [position, setPosition] = useState<[number, number] | null>(
    lat && lng ? [lat, lng] : (initialCenter || [23.6978, 120.9605])
  )

  useEffect(() => {
    if (lat && lng) {
      setPosition([lat, lng])
    }
  }, [lat, lng])

  const handleLocationChange = (newLat: number, newLng: number) => {
    setPosition([newLat, newLng])
    onChange(newLat, newLng)
  }

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" gutterBottom fontWeight={600}>
        📍 座標校正 (點擊地圖即可更新位置)
      </Typography>
      
      <Box sx={{ height: 300, width: '100%', borderRadius: 1, overflow: 'hidden', border: '1px solid #ddd' }}>
        <MapContainer
          center={position || [23.6978, 120.9605]}
          zoom={position ? 15 : 7}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap contributors'
          />
          <MapClickHandler onLocationSelect={handleLocationChange} />
          {position && <Marker position={position} draggable eventHandlers={{
            dragend: (e) => {
              const marker = e.target
              const pos = marker.getLatLng()
              handleLocationChange(pos.lat, pos.lng)
            }
          }} />}
        </MapContainer>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mt: 1.5 }}>
        <TextField
          label="緯度 (Lat)"
          size="small"
          type="number"
          value={lat || ''}
          onChange={(e) => onChange(Number(e.target.value), lng || 0)}
          fullWidth
          slotProps={{ htmlInput: { step: '0.000001' } }}
        />
        <TextField
          label="經度 (Lng)"
          size="small"
          type="number"
          value={lng || ''}
          onChange={(e) => onChange(lat || 0, Number(e.target.value))}
          fullWidth
          slotProps={{ htmlInput: { step: '0.000001' } }}
        />
      </Box>
    </Box>
  )
}
