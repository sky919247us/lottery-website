/**
 * 店家選擇器（中獎回報用）
 * 打開時先用 GPS 列出附近店家，打字則改用名稱/地址搜尋；皆為選填
 */

import { useEffect, useRef, useState } from 'react'
import { Autocomplete, TextField, CircularProgress } from '@mui/material'
import type { SxProps, Theme } from '@mui/material'
import { fetchNearbyRetailers, fetchRetailers } from '../hooks/api'
import type { RetailerData } from '../hooks/api'

interface RetailerPickerProps {
    value: RetailerData | null
    onChange: (retailer: RetailerData | null) => void
    sx?: SxProps<Theme>
}

export default function RetailerPicker({ value, onChange, sx }: RetailerPickerProps) {
    const [inputValue, setInputValue] = useState('')
    const [options, setOptions] = useState<RetailerData[]>([])
    const [nearby, setNearby] = useState<RetailerData[]>([])
    const [loading, setLoading] = useState(false)
    const nearbyRequested = useRef(false)

    /** 第一次打開時取附近店家（GPS 失敗就等使用者打字搜尋） */
    function loadNearby() {
        if (nearbyRequested.current || !navigator.geolocation) return
        nearbyRequested.current = true
        setLoading(true)
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                fetchNearbyRetailers(pos.coords.latitude, pos.coords.longitude, 2, 20)
                    .then((list) => {
                        setNearby(list)
                        setOptions((prev) => (prev.length ? prev : list))
                    })
                    .catch(() => { /* 靜默 */ })
                    .finally(() => setLoading(false))
            },
            () => setLoading(false),
            { timeout: 5000 },
        )
    }

    // 打字搜尋（防抖 300ms）；清空時回到附近清單
    useEffect(() => {
        const keyword = inputValue.trim()
        if (value && inputValue === value.name) return
        if (keyword.length < 2) {
            setOptions(nearby)
            return
        }
        const t = setTimeout(() => {
            setLoading(true)
            fetchRetailers({ search: keyword, limit: 20 })
                .then(setOptions)
                .catch(() => setOptions([]))
                .finally(() => setLoading(false))
        }, 300)
        return () => clearTimeout(t)
    }, [inputValue, nearby, value])

    return (
        <Autocomplete
            size="small"
            options={options}
            value={value}
            onOpen={loadNearby}
            onChange={(_, val) => onChange(val)}
            inputValue={inputValue}
            onInputChange={(_, val) => setInputValue(val)}
            filterOptions={(x) => x}
            getOptionLabel={(opt) => opt.name}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            renderOption={(props, opt) => (
                <li {...props} key={opt.id}>
                    <div>
                        <div>{opt.name}</div>
                        <div style={{ fontSize: 12, opacity: 0.7 }}>{opt.address}</div>
                    </div>
                </li>
            )}
            noOptionsText={inputValue.trim().length < 2 ? '輸入店名或地址搜尋' : '找不到店家'}
            loading={loading}
            sx={{ flex: 1, minWidth: 180, ...sx }}
            renderInput={(params) => (
                <TextField
                    {...params}
                    placeholder="在哪間店買的（選填）"
                    InputProps={{
                        ...params.InputProps,
                        endAdornment: (
                            <>
                                {loading ? <CircularProgress size={16} /> : null}
                                {params.InputProps.endAdornment}
                            </>
                        ),
                    }}
                />
            )}
        />
    )
}
