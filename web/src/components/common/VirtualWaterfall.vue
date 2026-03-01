<script lang="ts">
export interface WaterfallItem {
  id: number | string
  width: number
  height: number
  [key: string]: any
}
</script>

<script setup lang="ts" generic="T extends WaterfallItem">
import { ref, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import { useElementSize } from '@vueuse/core'

const props = defineProps<{
  items: T[]
  columnWidth?: number
  gap?: number
  buffer?: number
}>()

const emit = defineEmits(['load-more'])

const columnWidth = props.columnWidth || 280
const gap = props.gap || 16
const buffer = props.buffer || 800 // px buffer for virtual scroll

const containerRef = ref<HTMLElement | null>(null)
const { width: containerWidth } = useElementSize(containerRef)

const scrollContainerRef = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportHeight = ref(0)

// Calculate how many columns fit
const columnsCount = computed(() => {
  if (!containerWidth.value) return 5
  return Math.max(1, Math.floor((containerWidth.value + gap) / (columnWidth + gap)))
})

// Current column width considering container size and gap
const actualColumnWidth = computed(() => {
  if (!containerWidth.value) return columnWidth
  return (containerWidth.value - (columnsCount.value - 1) * gap) / columnsCount.value
})

interface LayoutItem {
  id: number | string
  top: number
  left: number
  width: number
  height: number
  item: T
}

const layoutItems = shallowRef<LayoutItem[]>([])
const totalHeight = ref(0)
const colHeights = ref<number[]>([])

// Recalculate layout for all items or append new ones
const calculateLayout = (isAppend = false) => {
  if (!containerWidth.value || props.items.length === 0) {
    layoutItems.value = []
    totalHeight.value = 0
    colHeights.value = new Array(columnsCount.value).fill(0)
    return
  }

  if (!isAppend || colHeights.value.length !== columnsCount.value) {
    colHeights.value = new Array(columnsCount.value).fill(0)
    layoutItems.value = []
  }

  const startIdx = layoutItems.value.length
  const newLayout: LayoutItem[] = isAppend ? [...layoutItems.value] : []

  for (let i = startIdx; i < props.items.length; i++) {
    const item = props.items[i]
    // Find the shortest column
    let minHeight = colHeights.value[0]
    let colIndex = 0
    for (let j = 1; j < colHeights.value.length; j++) {
      if (colHeights.value[j] < minHeight) {
        minHeight = colHeights.value[j]
        colIndex = j
      }
    }

    // Calculate height based on actual column width
    const ratio = item.height / item.width
    const itemHeight = actualColumnWidth.value * ratio
    const extraHeight = 64

    newLayout.push({
      id: item.id,
      top: minHeight,
      left: colIndex * (actualColumnWidth.value + gap),
      width: actualColumnWidth.value,
      height: itemHeight + extraHeight,
      item
    })

    colHeights.value[colIndex] += itemHeight + extraHeight + gap
  }

  layoutItems.value = newLayout
  totalHeight.value = Math.max(...colHeights.value)
}

// Visible items based on scroll position
const visibleItems = computed(() => {
  const start = scrollTop.value - buffer
  const end = scrollTop.value + viewportHeight.value + buffer

  return layoutItems.value.filter(item => {
    const itemBottom = item.top + item.height
    return itemBottom >= start && item.top <= end
  })
})

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  scrollTop.value = target.scrollTop
  viewportHeight.value = target.clientHeight

  // Check if near bottom to load more
  if (scrollTop.value + viewportHeight.value >= totalHeight.value - 200) {
    emit('load-more')
  }
}

// Initial size and scroll container identification
onMounted(() => {
  // Find the scrolling parent
  let parent = containerRef.value?.parentElement
  while (parent && parent !== document.documentElement) {
    const overflowY = window.getComputedStyle(parent).overflowY
    if (overflowY === 'auto' || overflowY === 'scroll') {
      scrollContainerRef.value = parent
      break
    }
    parent = parent.parentElement
  }

  if (!scrollContainerRef.value) {
    scrollContainerRef.value = document.documentElement
  }

  scrollContainerRef.value.addEventListener('scroll', handleScroll)
  viewportHeight.value = scrollContainerRef.value.clientHeight
  scrollTop.value = scrollContainerRef.value.scrollTop
  
  calculateLayout()
})

onUnmounted(() => {
  scrollContainerRef.value?.removeEventListener('scroll', handleScroll)
})

watch([containerWidth, columnsCount], () => {
  calculateLayout()
})

watch(() => props.items, (newItems, oldItems) => {
  const isAppend = newItems.length > oldItems.length && oldItems.length > 0 && newItems[0] === oldItems[0]
  calculateLayout(isAppend)
}, { deep: false })

</script>

<template>
  <div ref="containerRef" class="virtual-waterfall-container" :style="{ height: totalHeight + 'px' }">
    <transition-group name="waterfall">
      <div 
        v-for="item in visibleItems" 
        :key="item.id" 
        class="virtual-waterfall-item"
        :style="{
          position: 'absolute',
          top: item.top + 'px',
          left: item.left + 'px',
          width: item.width + 'px',
          height: item.height + 'px'
        }"
      >
        <slot :item="item.item"></slot>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.virtual-waterfall-container {
  position: relative;
  width: 100%;
}

.virtual-waterfall-item {
  will-change: transform, opacity;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease;
}

/* 瀑布流动画 */
.waterfall-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.waterfall-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.waterfall-move {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
