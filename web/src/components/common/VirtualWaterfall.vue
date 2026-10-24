<script lang="ts">
export interface WaterfallItem {
  id: number | string
  width: number
  height: number
  [key: string]: any
}
</script>

<script setup lang="ts" generic="T extends WaterfallItem">
import { ref, computed, onMounted, onUnmounted, watch, shallowRef, triggerRef } from 'vue'
import { useElementSize } from '@vueuse/core'

const props = defineProps<{
  items: T[]
  itemsVersion?: number
  columnWidth?: number
  gap?: number
  buffer?: number
  /** Fixed height reserved below the image for title/meta content. */
  metaHeight?: number
}>()

const emit = defineEmits(['load-more'])

const gapValue = props.gap ?? 16
const bufferValue = props.buffer ?? 800

const containerRef = ref<HTMLElement | null>(null)
const { width: containerWidth } = useElementSize(containerRef)

const scrollContainerRef = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportHeight = ref(0)

const columnsCount = computed(() => {
  if (!containerWidth.value) return 5
  const baseWidth = props.columnWidth || 280
  return Math.max(1, Math.floor((containerWidth.value + gapValue) / (baseWidth + gapValue)))
})

const actualColumnWidth = computed(() => {
  if (!containerWidth.value) return props.columnWidth || 280
  return (containerWidth.value - (columnsCount.value - 1) * gapValue) / columnsCount.value
})

interface LayoutItem {
  id: number | string
  top: number
  left: number
  width: number
  height: number
  index: number
  item: T
}

const layoutItems = shallowRef<LayoutItem[]>([])
const totalHeight = ref(0)

// Plain array: layout math does not need Vue reactivity for each column height.
let colHeights: number[] = []

const resetLayout = () => {
  colHeights = new Array(columnsCount.value).fill(0)
  layoutItems.value = []
}

const calculateLayout = (isAppend = false) => {
  if (!containerWidth.value || props.items.length === 0) {
    resetLayout()
    totalHeight.value = 0
    return
  }

  const columnsChanged = colHeights.length !== columnsCount.value
  const listShrunk = layoutItems.value.length > props.items.length

  if (!isAppend || columnsChanged || listShrunk) {
    resetLayout()
  }

  const layout = layoutItems.value
  const startIdx = layout.length
  const width = actualColumnWidth.value
  const metaHeight = props.metaHeight ?? 64

  for (let i = startIdx; i < props.items.length; i++) {
    const item = props.items[i]
    let minHeight = colHeights[0]
    let colIndex = 0
    for (let j = 1; j < colHeights.length; j++) {
      if (colHeights[j] < minHeight) {
        minHeight = colHeights[j]
        colIndex = j
      }
    }

    // Unreadable images may report 0x0; fall back to a 4:3 placeholder ratio.
    const sourceWidth = Number(item.width) || 0
    const sourceHeight = Number(item.height) || 0
    const ratio = sourceWidth > 0 && sourceHeight > 0 ? sourceHeight / sourceWidth : 0.75
    const imageHeight = width * ratio
    const itemHeight = imageHeight + metaHeight

    layout.push({
      id: item.id,
      top: minHeight,
      left: colIndex * (width + gapValue),
      width,
      height: itemHeight,
      index: i,
      item
    })

    colHeights[colIndex] += itemHeight + gapValue
  }

  if (isAppend) {
    // Mutate in place and notify Vue once. Avoids an O(n) array copy on every page append.
    triggerRef(layoutItems)
  } else {
    layoutItems.value = layout
  }

  totalHeight.value = colHeights.length ? Math.max(...colHeights) : 0
  maybeLoadMore()
}

const lowerBoundByTop = (list: LayoutItem[], value: number) => {
  let low = 0
  let high = list.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (list[mid].top < value) low = mid + 1
    else high = mid
  }
  return low
}

const upperBoundByTop = (list: LayoutItem[], value: number) => {
  let low = 0
  let high = list.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (list[mid].top <= value) low = mid + 1
    else high = mid
  }
  return low
}

// Only walk the items intersecting the viewport instead of filtering the whole list.
const visibleItems = computed(() => {
  const list = layoutItems.value
  if (!list.length) return []

  const start = scrollTop.value - bufferValue
  const end = scrollTop.value + viewportHeight.value + bufferValue

  let startIdx = lowerBoundByTop(list, start)
  while (startIdx > 0 && list[startIdx - 1].top + list[startIdx - 1].height >= start) {
    startIdx--
  }

  const endIdx = upperBoundByTop(list, end)
  return list.slice(startIdx, endIdx)
})

let lastLoadMoreAt = 0

const maybeLoadMore = () => {
  if (!props.items.length || !viewportHeight.value) return
  if (scrollTop.value + viewportHeight.value < totalHeight.value - 200) return

  const now = performance.now()
  if (now - lastLoadMoreAt < 250) return
  lastLoadMoreAt = now
  emit('load-more')
}

let scrollRaf = 0
let resizeTimer = 0
let layoutTimer = 0
let pendingScrollTop = 0
let pendingViewportHeight = 0

const flushScroll = () => {
  scrollRaf = 0
  scrollTop.value = pendingScrollTop
  viewportHeight.value = pendingViewportHeight
  maybeLoadMore()
}

const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement
  pendingScrollTop = target.scrollTop
  pendingViewportHeight = target.clientHeight
  if (!scrollRaf) {
    scrollRaf = requestAnimationFrame(flushScroll)
  }
}

const syncViewport = () => {
  const container = scrollContainerRef.value
  if (!container) return
  pendingScrollTop = container.scrollTop
  pendingViewportHeight = container.clientHeight
  scrollTop.value = pendingScrollTop
  viewportHeight.value = pendingViewportHeight
}

const handleResize = () => {
  syncViewport()
  // Coalesce resize bursts; a full relayout of a very large loaded list is expensive.
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => {
    resizeTimer = 0
    calculateLayout()
  }, 120)
}

const scheduleLayout = () => {
  if (layoutTimer) clearTimeout(layoutTimer)
  layoutTimer = window.setTimeout(() => {
    layoutTimer = 0
    calculateLayout()
  }, 80)
}

let lastItems: T[] | null = null
let lastLength = 0

onMounted(() => {
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

  scrollContainerRef.value.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('resize', handleResize, { passive: true })

  syncViewport()
  lastItems = props.items
  lastLength = props.items.length
  calculateLayout()
})

onUnmounted(() => {
  scrollContainerRef.value?.removeEventListener('scroll', handleScroll)
  window.removeEventListener('resize', handleResize)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
  if (resizeTimer) clearTimeout(resizeTimer)
  if (layoutTimer) clearTimeout(layoutTimer)
})

watch([containerWidth, columnsCount, () => props.columnWidth, () => props.metaHeight], () => {
  scheduleLayout()
})

watch([() => props.items, () => props.items.length, () => props.itemsVersion], ([items, length]) => {
  const isAppend = items === lastItems && lastItems !== null && length > lastLength
  lastItems = items
  lastLength = length
  calculateLayout(isAppend)
})
</script>

<template>
  <div
    ref="containerRef"
    class="virtual-waterfall-container"
    :style="{ height: totalHeight + 'px' }"
  >
    <div
      v-for="item in visibleItems"
      :key="item.id"
      class="virtual-waterfall-item"
      :style="{
        top: item.top + 'px',
        left: item.left + 'px',
        width: item.width + 'px',
        height: item.height + 'px'
      }"
    >
      <slot :item="item.item" :index="item.index"></slot>
    </div>
  </div>
</template>

<style scoped>
.virtual-waterfall-container {
  position: relative;
  width: 100%;
}

.virtual-waterfall-item {
  position: absolute;
  /* 不使用 paint containment：否则卡片 hover 抬升与外侧阴影/描边会被裁掉 */
  contain: layout style;
}
</style>
