<script setup>
import { AlertCircle, Bookmark, LoaderCircle, NotebookPen, SearchX } from '@lucide/vue'

defineProps({
  kind: { type: String, required: true },
  title: { type: String, required: true },
})
const icons = { loading: LoaderCircle, error: AlertCircle, search: SearchX, favorites: Bookmark, notes: NotebookPen }
</script>

<template>
  <div class="status" :role="kind === 'error' ? 'alert' : 'status'">
    <span class="status-icon" :class="{ 'error-symbol': kind === 'error' }">
      <component :is="icons[kind] || AlertCircle" :size="27" :class="{ spinning: kind === 'loading' }" />
    </span>
    <p>{{ title }}</p>
    <slot />
  </div>
</template>
