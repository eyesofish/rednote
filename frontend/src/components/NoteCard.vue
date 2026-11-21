<script setup>
import { ArrowUpRight } from '@lucide/vue'
import { publishedDate } from '../api'

defineProps({ note: { type: Object, required: true } })
</script>

<template>
  <article class="note-card">
    <RouterLink :to="{ name: 'detail', params: { id: note.id } }" class="card-link">
      <div class="card-cover"><img :src="note.cover_url" alt="" loading="lazy" /></div>
      <div class="card-title"><h2>{{ note.title }}</h2><ArrowUpRight :size="20" aria-hidden="true" /></div>
    </RouterLink>
    <div class="card-meta">
      <span class="byline">
        <span class="avatar" aria-hidden="true">{{ (note.author_name || '笔').slice(0, 1) }}</span>
        {{ note.author_name }}
      </span>
      <time :datetime="note.published_at">{{ publishedDate(note.published_at) }}</time>
    </div>
  </article>
</template>
