<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ImageGrid from '@/components/ImageGrid.vue'
import AdminPage from '@/pages/AdminPage.vue'
import Lightbox from '@/components/Lightbox.vue'
import { ref, computed } from 'vue'
import { useImageStore } from '@/stores/image'
import { storeToRefs } from 'pinia'

const imageStore = useImageStore()
const { images, total, loading, showAdminView } = storeToRefs(imageStore)

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
const hasNext = computed(() => {
  if (currentIndex.value === -1) return false
  // Either we have a next image in current list, or we have more to load from server
  return currentIndex.value < images.value.length - 1 || images.value.length < total.value
})

const prevImage = computed(() => hasPrev.value ? images.value[currentIndex.value - 1] : null)
const nextImage = computed(() => (currentIndex.value < images.value.length - 1) ? images.value[currentIndex.value + 1] : null)

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

const handleNext = async () => {
  if (currentIndex.value < images.value.length - 1) {
    // We already have the next image loaded
    const nextImg = images.value[currentIndex.value + 1]
    currentImageId.value = nextImg.id
    
    // Check if we need to load more images for later
    if (currentIndex.value > images.value.length - 10 && images.value.length < total.value && !loading.value) {
      imageStore.fetchImages()
    }
  } else if (images.value.length < total.value) {
    // We are at the end but there are more images on server
    if (!loading.value) {
      const oldLength = images.value.length
      await imageStore.fetchImages()
      if (images.value.length > oldLength) {
        currentImageId.value = images.value[oldLength].id
      }
    }
  }
}
</script>

<template>
  <div class="app-container">
    <Sidebar />
    <main class="main-content">
      <TopBar />
      <transition name="fade-slide" mode="out-in">
        <ImageGrid v-if="!showAdminView" @open-lightbox="handleOpenLightbox" />
        <AdminPage v-else />
      </transition>
    </main>
    
    <transition name="lightbox-fade">
      <Lightbox 
        v-if="showLightbox && currentImage"
        :visible="true"
        :image="currentImage"
        :prev-image="prevImage"
        :next-image="nextImage"
        :has-prev="hasPrev"
        :has-next="hasNext"
        :current-index="currentIndex"
        :total-images="total"
        :loading="loading"
        @close="showLightbox = false"
        @prev="handlePrev"
        @next="handleNext"
      />
    </transition>
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

/* 视图切换动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

/* 灯箱淡入淡出 */
.lightbox-fade-enter-active,
.lightbox-fade-leave-active {
  transition: opacity 0.3s ease;
}

.lightbox-fade-enter-from,
.lightbox-fade-leave-to {
  opacity: 0;
}
</style>
