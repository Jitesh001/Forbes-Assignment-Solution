import { ref, onMounted, onUnmounted } from 'vue'
import { fetchLatestRates, fetchRateHistory } from '../api/rates'

export function useLatestRates(refreshInterval = 60000) {
  const rates = ref([])
  const loading = ref(false)
  const error = ref(null)
  let timer = null

  async function load(type = null) {
    loading.value = true
    error.value = null
    try {
      rates.value = await fetchLatestRates(type)
    } catch (err) {
      error.value = err.response?.data?.error || err.message || 'Failed to load rates'
    } finally {
      loading.value = false
    }
  }

  function startAutoRefresh(type = null) {
    stopAutoRefresh()
    timer = setInterval(() => load(type), refreshInterval)
  }

  function stopAutoRefresh() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onUnmounted(stopAutoRefresh)

  return { rates, loading, error, load, startAutoRefresh, stopAutoRefresh }
}

export function useRateHistory() {
  const history = ref([])
  const loading = ref(false)
  const error = ref(null)
  const pagination = ref({ count: 0, next: null, previous: null })

  async function load(provider, type, from = null, to = null, page = 1) {
    loading.value = true
    error.value = null
    try {
      const data = await fetchRateHistory(provider, type, from, to, page)
      history.value = data.results || []
      pagination.value = {
        count: data.count || 0,
        next: data.next,
        previous: data.previous,
      }
    } catch (err) {
      error.value = err.response?.data?.error || err.message || 'Failed to load history'
      history.value = []
    } finally {
      loading.value = false
    }
  }

  return { history, loading, error, pagination, load }
}
