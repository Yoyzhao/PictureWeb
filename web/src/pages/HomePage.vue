<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ImageGrid from '@/components/ImageGrid.vue'
import Lightbox from '@/components/Lightbox.vue'
import { ref, computed } from 'vue'
import { useImageStore } from '@/stores/image'
import { storeToRefs } from 'pinia'

const imageStore = useImageStore()
const { images } = storeToRefs(imageStore)

const showLightbox = ref(false)
const currentImageId = ref<number | null>(null)

const currentImage = computed(() => {
  if (currentImageId.value === null) return null
  return images.value.find(img => img.id === currentImageId.value) || null
})

const currentIndex = computed(() => {
  if (!currentImage.value) return -1
  return images.value.findIndex(img => img.id === currentImage.value?.id)
})

const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < images.value.length - 1 && currentIndex.value !== -1)

const handleOpenLightbox = (image: any) => {
  currentImageId.value = image.id
  showLightbox.value = true
}

const handlePrev = () => {
  if (hasPrev.value) {
    const prevImg = images.value[currentIndex.value - 1]
    currentImageId.value = prevImg.id
  }
}

const handleNext = () => {
  if (hasNext.value) {
    const nextImg = images.value[currentIndex.value + 1]
    currentImageId.value = nextImg.id
  }
}
</script>

<template>
  <div class="app-container">
    <Sidebar />
    <main class="main-content">
      <TopBar />
      <ImageGrid @open-lightbox="handleOpenLightbox" />
    </main>
    
    <Lightbox 
      v-if="showLightbox && currentImage"
      :visible="true"
      :image="currentImage"
      :has-prev="hasPrev"
      :has-next="hasNext"
      @close="showLightbox = false"
      @prev="handlePrev"
      @next="handleNext"
    />
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--bg-main);
  color: var(--text-primary);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
</style>
