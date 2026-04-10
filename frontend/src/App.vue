<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">Rate Tracker</h1>
            <p class="text-sm text-gray-500 mt-1">Interest rate monitoring dashboard</p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
              :class="autoRefreshActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
            >
              <span
                class="w-2 h-2 rounded-full"
                :class="autoRefreshActive ? 'bg-green-500 animate-pulse' : 'bg-gray-400'"
              ></span>
              {{ autoRefreshActive ? 'Live' : 'Paused' }}
            </span>
            <span class="text-xs text-gray-400" v-if="lastUpdated">
              Updated {{ lastUpdated }}
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- Main content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <!-- Rate Type Filter -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="opt in typeOptions"
          :key="opt.value"
          @click="selectType(opt.value)"
          class="px-3 py-1.5 text-sm rounded-lg border transition-colors"
          :class="selectedType === opt.value
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'"
        >
          {{ opt.label }}
        </button>
      </div>

      <!-- Latest Rates Table -->
      <RateTable
        :rates="latestRates"
        :loading="latestLoading"
        :error="latestError"
        @select-provider="onSelectProvider"
      />

      <!-- History Chart -->
      <RateHistoryChart
        :provider="selectedProvider"
        :rate-type="selectedHistoryType"
        :key="selectedProvider + selectedHistoryType"
      />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import RateTable from './components/RateTable.vue'
import RateHistoryChart from './components/RateHistoryChart.vue'
import { useLatestRates } from './composables/useRates'

const typeOptions = [
  { value: null, label: 'All Types' },
  { value: '30yr_fixed_mortgage', label: '30-Year Fixed' },
  { value: '15yr_fixed_mortgage', label: '15-Year Fixed' },
  { value: '5yr_arm_mortgage', label: '5-Year ARM' },
  { value: 'savings_1yr_fixed', label: 'Savings 1-Year' },
  { value: 'savings_easy_access', label: 'Savings Easy Access' },
]

const selectedType = ref(null)
const selectedProvider = ref(null)
const selectedHistoryType = ref('30yr_fixed_mortgage')
const lastUpdated = ref(null)
const autoRefreshActive = ref(true)

const {
  rates: latestRates,
  loading: latestLoading,
  error: latestError,
  load: loadLatest,
  startAutoRefresh,
} = useLatestRates(60000)

function selectType(type) {
  selectedType.value = type
  loadLatest(type)
  startAutoRefresh(type)
  updateTimestamp()
}

function onSelectProvider({ provider, rateType }) {
  selectedProvider.value = provider
  selectedHistoryType.value = rateType
}

function updateTimestamp() {
  lastUpdated.value = new Date().toLocaleTimeString()
}

// Initial load + auto-refresh patch to track timestamp
const origLoad = loadLatest
async function loadAndTrack(type) {
  await origLoad(type)
  updateTimestamp()
}

onMounted(async () => {
  await loadAndTrack(null)
  startAutoRefresh(null)
})
</script>
