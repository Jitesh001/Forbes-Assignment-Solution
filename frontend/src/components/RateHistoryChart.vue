<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
    <div class="px-4 sm:px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">30-Day Rate History</h2>
        <p class="text-sm text-gray-500 mt-0.5" v-if="provider">
          {{ provider }} &mdash; {{ formatType(rateType) }}
        </p>
        <p class="text-sm text-gray-500 mt-0.5" v-else>
          Select a provider from the table above
        </p>
      </div>
      <div v-if="provider" class="flex items-center gap-2">
        <select
          v-model="selectedType"
          @change="loadHistory"
          class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <div class="p-4 sm:p-6">
      <!-- No provider selected -->
      <div v-if="!provider" class="h-64 flex items-center justify-center text-gray-400">
        <p>Click a row in the table to view rate history</p>
      </div>

      <!-- Loading -->
      <div v-else-if="loading" class="h-64 flex items-center justify-center">
        <div class="inline-flex items-center gap-2 text-gray-500">
          <svg class="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
          </svg>
          <span>Loading history...</span>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="h-64 flex items-center justify-center">
        <div class="text-center">
          <p class="text-red-600 font-medium">{{ error }}</p>
          <button @click="loadHistory" class="mt-2 text-sm text-blue-600 hover:text-blue-800 underline">
            Retry
          </button>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="!history.length" class="h-64 flex items-center justify-center text-gray-400">
        <p>No history data available for this selection</p>
      </div>

      <!-- Chart -->
      <div v-else class="h-64 sm:h-80">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { useRateHistory } from '../composables/useRates'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const props = defineProps({
  provider: { type: String, default: null },
  rateType: { type: String, default: '30yr_fixed_mortgage' },
})

const typeOptions = [
  { value: '30yr_fixed_mortgage', label: '30-Year Fixed' },
  { value: '15yr_fixed_mortgage', label: '15-Year Fixed' },
  { value: '5yr_arm_mortgage', label: '5-Year ARM' },
  { value: 'savings_1yr_fixed', label: 'Savings 1-Year' },
  { value: 'savings_easy_access', label: 'Savings Easy Access' },
]

const selectedType = ref(props.rateType)
const { history, loading, error, load } = useRateHistory()

const TYPE_LABELS = {
  '30yr_fixed_mortgage': '30-Year Fixed Mortgage',
  '15yr_fixed_mortgage': '15-Year Fixed Mortgage',
  '5yr_arm_mortgage': '5-Year ARM Mortgage',
  'savings_1yr_fixed': 'Savings 1-Year Fixed',
  'savings_easy_access': 'Savings Easy Access',
}

function formatType(t) { return TYPE_LABELS[t] || t }

function getLast30DayRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 30)
  return {
    from: from.toISOString().split('T')[0],
    to: to.toISOString().split('T')[0],
  }
}

async function loadHistory() {
  if (!props.provider) return
  const { from, to } = getLast30DayRange()
  // Load all pages for the chart (up to 500 points)
  await load(props.provider, selectedType.value, from, to, 1)
}

const chartData = computed(() => ({
  labels: history.value.map((r) => r.effective_date),
  datasets: [
    {
      label: `${props.provider} - ${formatType(selectedType.value)}`,
      data: history.value.map((r) => parseFloat(r.rate_value)),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 2,
      pointHoverRadius: 5,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false,
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.parsed.y.toFixed(4)}%`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { maxTicksLimit: 10, font: { size: 11 } },
    },
    y: {
      ticks: {
        callback: (v) => `${v}%`,
        font: { size: 11 },
      },
    },
  },
}

watch(() => props.provider, loadHistory)
watch(() => props.rateType, (val) => {
  selectedType.value = val
  loadHistory()
})

onMounted(loadHistory)
</script>
