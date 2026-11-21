<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDownWideNarrow, RotateCcw } from '@lucide/vue'
import { request, readableError } from '../api'
import NoteCard from '../components/NoteCard.vue'
import StatusPanel from '../components/StatusPanel.vue'

const route = useRoute()
const items = ref([])
const loading = ref(false)
const error = ref('')
const term = computed(() => String(route.query.q || '').trim())
const title = computed(() => ({ home: '发现笔记', favorites: '我的收藏', search: '搜索笔记' }[route.name]))
let current
onUnmounted(() => current?.abort())

async function load() {
  current?.abort()
  const controller = new AbortController()
  current = controller
  items.value = []
  error.value = ''
  const mode = route.name
  if (mode === 'search' && !term.value) {
    loading.value = false
    return
  }
  loading.value = true
  const path = mode === 'search' ? '/search?q=' + encodeURIComponent(term.value)
    : mode === 'favorites' ? '/me/favorites' : '/notes'
  try {
    const data = await request(path, { signal: controller.signal })
    if (!controller.signal.aborted) items.value = data.items
  } catch (e) {
    if (!controller.signal.aborted) {
      error.value = mode === 'search' && e.status === 503
        ? '搜索暂时不可用，请稍后再试' : readableError(e, '笔记加载失败，请重试')
    }
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}
watch(term, load, { immediate: true })
</script>

<template>
  <section>
    <div class="section-heading">
      <h1>{{ title }}</h1>
      <span v-if="route.name === 'home'" class="sort"><ArrowDownWideNarrow :size="17" />最新发布</span>
      <span v-else-if="route.name === 'search' && term" class="search-term">“{{ term }}”</span>
    </div>
    <StatusPanel v-if="loading" kind="loading" title="正在加载笔记…" />
    <StatusPanel v-else-if="error" kind="error" :title="error">
      <button class="btn secondary" @click="load"><RotateCcw :size="15" />重试</button>
    </StatusPanel>
    <div v-else-if="items.length" class="note-grid" aria-label="笔记列表">
      <NoteCard v-for="note in items" :key="note.id" :note="note" />
    </div>
    <StatusPanel v-else-if="route.name === 'search'" kind="search" :title="term ? '没有找到相关笔记' : '请输入搜索关键词'" />
    <StatusPanel v-else-if="route.name === 'favorites'" kind="favorites" title="还没有收藏的笔记">
      <RouterLink class="btn secondary" to="/">去发现笔记</RouterLink>
    </StatusPanel>
    <StatusPanel v-else kind="notes" title="这里还没有笔记"><RouterLink class="btn accent" to="/notes/new">写第一篇笔记</RouterLink></StatusPanel>
  </section>
</template>
