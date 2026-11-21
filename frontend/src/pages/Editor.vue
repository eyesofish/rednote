<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ImagePlus, X } from '@lucide/vue'
import { readableError, request } from '../api'
import { user } from '../session'
import StatusPanel from '../components/StatusPanel.vue'

const route = useRoute()
const router = useRouter()
const noteId = route.params.id
const editing = Boolean(noteId)
const title = ref('')
const body = ref('')
const originalImages = ref([])
const files = ref([])
const loading = ref(editing)
const busy = ref(false)
const loadError = ref('')
const error = ref('')
const returnTo = computed(() => editing ? '/notes/' + noteId : '/')

async function load() {
  if (!editing) return
  loading.value = true
  try {
    const note = await request('/notes/' + noteId)
    if (note.author_id !== user.value?.id) {
      loadError.value = '只有作者可以修改这篇笔记'
      return
    }
    title.value = note.title
    body.value = note.body
    originalImages.value = note.images
  } catch (e) {
    loadError.value = readableError(e)
  } finally {
    loading.value = false
  }
}
function chooseFiles(event) {
  const chosen = Array.from(event.target.files)
  event.target.value = ''
  if (!chosen.length) return
  if (chosen.length + files.value.length > 4 || chosen.some(f => !['image/jpeg', 'image/png', 'image/webp'].includes(f.type) || f.size > 4 * 1024 * 1024)) {
    error.value = '最多选择 4 张 JPG、PNG 或 WebP 图片，每张不超过 4 MiB'
    return
  }
  error.value = ''
  files.value.push(...chosen.map(file => ({ file, url: URL.createObjectURL(file) })))
}
function removeFile(index) {
  URL.revokeObjectURL(files.value[index].url)
  files.value.splice(index, 1)
}
async function submit() {
  if (busy.value) return
  if (!title.value.trim() || !body.value.trim() || (!editing && !files.value.length)) {
    error.value = '请填写标题、正文，并至少选择一张图片'
    return
  }
  const data = new FormData()
  data.append('title', title.value.trim())
  data.append('body', body.value.trim())
  for (const item of files.value) data.append('images', item.file)
  busy.value = true
  error.value = ''
  try {
    const note = await request(editing ? '/notes/' + noteId : '/notes', { method: editing ? 'PATCH' : 'POST', body: data })
    await router.replace({ name: 'detail', params: { id: note.id } })
  } catch (e) {
    error.value = readableError(e)
  } finally {
    busy.value = false
  }
}
onMounted(load)
onUnmounted(() => files.value.forEach(item => URL.revokeObjectURL(item.url)))
</script>

<template>
  <RouterLink class="back" :to="returnTo"><ArrowLeft :size="16" />{{ editing ? '返回详情' : '发现笔记' }}</RouterLink>
  <StatusPanel v-if="loading" kind="loading" title="正在打开笔记…" />
  <StatusPanel v-else-if="loadError" kind="error" :title="loadError" />
  <section v-else class="form-panel editor-panel">
    <h1>{{ editing ? '编辑笔记' : '写笔记' }}</h1>
    <form class="entry-form" @submit.prevent="submit">
      <div>
        <p class="field-title">配图</p>
        <div v-if="files.length || originalImages.length" class="image-previews">
          <div v-for="(item, i) in (files.length ? files : originalImages)" :key="item.url">
            <img :src="item.url" :alt="'配图 ' + (i + 1)" />
            <button v-if="files.length" type="button" :aria-label="'移除图片 ' + (i + 1)" @click="removeFile(i)"><X :size="14" /></button>
          </div>
        </div>
        <label class="file-picker"><ImagePlus :size="20" />{{ editing && !files.length ? '替换配图' : '选择图片' }}
          <input aria-label="选择笔记图片" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="chooseFiles" />
        </label>
        <p class="field-hint">1–4 张 JPG、PNG 或 WebP，每张最多 4 MiB。第一张将用作封面。</p>
      </div>
      <label>标题<input v-model="title" maxlength="160" required placeholder="给笔记起个标题" /></label>
      <label>正文<textarea v-model="body" maxlength="12000" rows="7" required placeholder="记下想分享的内容…" /></label>
      <p v-if="error" role="alert" class="notice error">{{ error }}</p>
      <div class="editor-actions"><RouterLink class="btn secondary" :to="returnTo">取消</RouterLink><button class="btn accent" :disabled="busy">{{ busy ? '正在保存…' : editing ? '保存修改' : '发布笔记' }}</button></div>
    </form>
  </section>
</template>
