import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import type { HeatmapPoint } from '../hooks/api'

export default function HeatmapLayer({ points }: { points: HeatmapPoint[] }) {
    const map = useMap()

    useEffect(() => {
        if (!points || points.length === 0) return

        // 將座標轉換為 [lat, lng, intensity] 的陣列
        // 這裡設定 intensity 以 jackpotCount 為主權重
        const maxJackpot = Math.max(...points.map(p => p.jackpotCount), 1)

        const heatArray = points.map(p => [
            p.lat,
            p.lng,
            // 正規化 intensity，加上底氣 (至少 0.2) 讓沒有頭獎的區域也能稍微顯示熱度
            (p.jackpotCount / maxJackpot) * 0.8 + 0.2
        ]) as L.HeatLatLngTuple[]

        const heatLayer = L.heatLayer(heatArray, {
            radius: 25,
            blur: 15,
            maxZoom: 13,
            max: 1.0,
            gradient: {
                0.4: 'blue',
                0.6: 'lime',
                0.8: 'yellow',
                1.0: 'red'
            }
        })

        heatLayer.addTo(map)

        return () => {
            map.removeLayer(heatLayer)
        }
    }, [map, points])

    return null
}
