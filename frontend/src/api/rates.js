import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

export async function fetchLatestRates(type = null) {
  const params = {}
  if (type) params.type = type
  const { data } = await client.get('/rates/latest/', { params })
  return data
}

export async function fetchRateHistory(provider, type, from = null, to = null, page = 1) {
  const params = { provider, type, page }
  if (from) params.from = from
  if (to) params.to = to
  const { data } = await client.get('/rates/history/', { params })
  return data
}
