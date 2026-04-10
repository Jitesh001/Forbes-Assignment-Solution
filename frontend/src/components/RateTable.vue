<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
    <div class="px-4 sm:px-6 py-4 border-b border-gray-200">
      <h2 class="text-lg font-semibold text-gray-900">Latest Rates by Provider</h2>
      <p class="text-sm text-gray-500 mt-0.5">Click a row to view 30-day history</p>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="p-8 text-center">
      <div class="inline-flex items-center gap-2 text-gray-500">
        <svg class="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Loading rates...</span>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="p-8 text-center">
      <div class="inline-flex flex-col items-center gap-2">
        <svg class="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <p class="text-red-600 font-medium">{{ error }}</p>
        <button
          @click="$emit('retry')"
          class="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
        >
          Retry
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!rates.length" class="p-8 text-center text-gray-500">
      No rate data available.
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr class="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="px-4 sm:px-6 py-3 cursor-pointer hover:text-gray-700" @click="toggleSort('provider')">
              Provider
              <span v-if="sortField === 'provider'">{{ sortDir === 'asc' ? ' ▲' : ' ▼' }}</span>
            </th>
            <th class="px-4 sm:px-6 py-3">Type</th>
            <th class="px-4 sm:px-6 py-3 cursor-pointer hover:text-gray-700" @click="toggleSort('rate_value')">
              Rate (%)
              <span v-if="sortField === 'rate_value'">{{ sortDir === 'asc' ? ' ▲' : ' ▼' }}</span>
            </th>
            <th class="px-4 sm:px-6 py-3 cursor-pointer hover:text-gray-700 hidden sm:table-cell" @click="toggleSort('effective_date')">
              Effective Date
              <span v-if="sortField === 'effective_date'">{{ sortDir === 'asc' ? ' ▲' : ' ▼' }}</span>
            </th>
            <th class="px-4 sm:px-6 py-3 hidden md:table-cell">Currency</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr
            v-for="rate in sortedRates"
            :key="rate.id"
            @click="$emit('select-provider', { provider: rate.provider, rateType: rate.rate_type })"
            class="hover:bg-blue-50 cursor-pointer transition-colors"
          >
            <td class="px-4 sm:px-6 py-3 font-medium text-gray-900">{{ rate.provider }}</td>
            <td class="px-4 sm:px-6 py-3 text-gray-600">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="typeColor(rate.rate_type)">
                {{ formatType(rate.rate_type) }}
              </span>
            </td>
            <td class="px-4 sm:px-6 py-3 font-mono text-gray-900 font-semibold">
              {{ parseFloat(rate.rate_value).toFixed(2) }}%
            </td>
            <td class="px-4 sm:px-6 py-3 text-gray-600 hidden sm:table-cell">{{ rate.effective_date }}</td>
            <td class="px-4 sm:px-6 py-3 text-gray-500 hidden md:table-cell">{{ rate.currency }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  rates: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
})

defineEmits(['select-provider', 'retry'])

const sortField = ref('rate_value')
const sortDir = ref('desc')

function toggleSort(field) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = field === 'rate_value' ? 'desc' : 'asc'
  }
}

const sortedRates = computed(() => {
  const arr = [...props.rates]
  arr.sort((a, b) => {
    let aVal = a[sortField.value]
    let bVal = b[sortField.value]
    if (sortField.value === 'rate_value') {
      aVal = parseFloat(aVal)
      bVal = parseFloat(bVal)
    }
    if (aVal < bVal) return sortDir.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return arr
})

const TYPE_LABELS = {
  '30yr_fixed_mortgage': '30Y Fixed',
  '15yr_fixed_mortgage': '15Y Fixed',
  '5yr_arm_mortgage': '5Y ARM',
  'savings_1yr_fixed': 'Savings 1Y',
  'savings_easy_access': 'Savings EA',
}

const TYPE_COLORS = {
  '30yr_fixed_mortgage': 'bg-blue-100 text-blue-800',
  '15yr_fixed_mortgage': 'bg-indigo-100 text-indigo-800',
  '5yr_arm_mortgage': 'bg-purple-100 text-purple-800',
  'savings_1yr_fixed': 'bg-green-100 text-green-800',
  'savings_easy_access': 'bg-teal-100 text-teal-800',
}

function formatType(t) { return TYPE_LABELS[t] || t }
function typeColor(t) { return TYPE_COLORS[t] || 'bg-gray-100 text-gray-800' }
</script>
