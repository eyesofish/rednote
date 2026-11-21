<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Bookmark, Check, Pencil, Trash2 } from '@lucide/vue'
import { request, publishedDate, readableError } from '../api'
import { user } from '../session'
import StatusPanel from '../components/StatusPanel.vue'

const route = useRoute()
const router = useRouter()
const noteId = route.params.id
const note = ref(null)
const loading = ref(true)
const loadError = ref('')
const actionError = ref('')
const busy = ref(false)
const selectedImage = ref(0)
const dialog = ref(null)
const isAuthor = computed(() => note.value && user.value?.id === note.value.author_id)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    note.value = await request('/notes/' + noteId)
    document.title = note.value.title + ' · 页间'
  } catch (e) {
    loadError.value = readableError(e, '笔记加载失败，请重试')
  } finally {
    loading.value = false
  }
}
async function toggleFavorite() {
  if (!user.value) {
    await router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  if (busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    await request('/me/favorites/' + noteId, { method: note.value.is_favorite ? 'DELETE' : 'PUT' })
    note.value.is_favorite = !note.value.is_favorite
  } catch (e) {
    actionError.value = readableError(e)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    await request('/notes/' + noteId, { method: 'DELETE' })
    dialog.value.close()
    await router.replace('/')
  } catch (e) {
    dialog.value.close()
    actionError.value = readableError(e)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <RouterLink class="back" to="/"><ArrowLeft :size="16" />发现笔记</RouterLink>
  <StatusPanel v-if="loading" kind="loading" title="正在打开笔记…" />
  <StatusPanel v-else-if="loadError" kind="error" :title="loadError"><button class="btn secondary" @click="load">重试</button></StatusPanel>
  <article v-else-if="note" class="detail-layout">
    <div class="detail-gallery">
      <div class="detail-cover"><img :src="note.images[selectedImage]?.url || note.cover_url" :alt="note.title + '，图片 ' + (selectedImage + 1)" /></div>
      <div v-if="note.images.length > 1" class="thumbnails">
        <button v-for="(image, i) in note.images" :key="image.id" :aria-pressed="i === selectedImage" :aria-label="'查看图片 ' + (i + 1)" @click="selectedImage = i">
          <img :src="image.url" alt="" />
        </button>
      </div>
    </div>
    <div class="detail-copy">
      <div class="detail-meta">
        <span class="byline"><span class="avatar" aria-hidden="true">{{ note.author_name.slice(0, 1) }}</span>{{ note.author_name }}</span>
        <time :datetime="note.published_at">{{ publishedDate(note.published_at) }}</time>
      </div>
      <h1>{{ note.title }}</h1>
      <div class="detail-body">{{ note.body }}</div>
      <div class="detail-actions">
        <button class="btn" :class="note.is_favorite ? 'secondary' : 'accent'" :disabled="busy" :aria-pressed="note.is_favorite" @click="toggleFavorite">
          <component :is="note.is_favorite ? Check : Bookmark" :size="16" />{{ note.is_favorite ? '取消收藏' : '收藏笔记' }}
        </button>
        <template v-if="isAuthor">
          <RouterLink class="btn secondary" :to="{ name: 'edit', params: { id: noteId } }"><Pencil :size="15" />编辑</RouterLink>
          <button class="icon-button" aria-label="删除笔记" title="删除笔记" @click="dialog.showModal()"><Trash2 :size="17" /></button>
        </template>
      </div>
      <p v-if="actionError" role="alert" class="notice error">{{ actionError }}</p>
    </div>
    <dialog ref="dialog" class="confirm-dialog" aria-labelledby="delete-title">
      <h2 id="delete-title">删除这篇笔记？</h2>
      <p>《{{ note.title }}》也会从首页和收藏列表中移除。</p>
      <div class="dialog-actions">
        <button class="btn secondary" autofocus :disabled="busy" @click="dialog.close()">保留笔记</button>
        <button class="btn accent" :disabled="busy" @click="remove">确认删除</button>
      </div>
    </dialog>
  </article>
</template>
