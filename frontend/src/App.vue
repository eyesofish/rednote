<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bookmark, Compass, LogOut, Plus, Search, UserRound } from '@lucide/vue'
import { logout, user } from './session'

const route = useRoute()
const router = useRouter()
const query = ref('')
const searchRevision = ref(0)
const logoutError = ref('')

watch(() => route.fullPath, () => {
  query.value = route.name === 'search' ? String(route.query.q || '') : ''
  logoutError.value = ''
}, { immediate: true })

function search() {
  const q = query.value.trim()
  if (route.name === 'search' && String(route.query.q || '') === q) {
    searchRevision.value++
    return
  }
  router.push({ name: 'search', query: q ? { q } : {} })
}
async function signOut() {
  try {
    await logout()
    await router.replace('/')
  } catch {
    logoutError.value = '退出失败，请重试'
  }
}
</script>

<template>
  <a class="skip-link" href="#content">跳到正文</a>
  <header class="masthead">
    <div class="masthead-inner">
      <RouterLink to="/" class="brand" aria-label="页间首页">
        <img src="/mark.svg" alt="" width="38" height="38" /><span>页间</span>
      </RouterLink>
      <nav aria-label="主导航" class="primary-nav">
        <RouterLink to="/" :class="{ selected: route.name === 'home' }"><Compass :size="18" />发现</RouterLink>
        <RouterLink to="/favorites" :class="{ selected: route.name === 'favorites' }"><Bookmark :size="18" />我的收藏</RouterLink>
      </nav>
      <form class="search-form" role="search" @submit.prevent="search">
        <input v-model="query" aria-label="搜索关键词" placeholder="搜索图文笔记" type="search" maxlength="120" />
        <button aria-label="搜索" title="搜索"><Search :size="18" /></button>
      </form>
      <RouterLink to="/notes/new" class="btn accent compose"><Plus :size="18" /><span>写笔记</span></RouterLink>
      <div v-if="user" class="account-control">
        <span class="avatar avatar-account" :title="user.display_name" :aria-label="user.display_name">{{ user.display_name.slice(0, 1) }}</span>
        <button class="icon-button" title="退出登录" aria-label="退出登录" @click="signOut"><LogOut :size="18" /></button>
      </div>
      <RouterLink v-else :to="{ name: 'login', query: route.name === 'login' ? {} : { next: route.fullPath } }" class="login-link">
        <UserRound :size="17" /><span>登录</span>
      </RouterLink>
    </div>
  </header>
  <main id="content" class="page" tabindex="-1">
    <p v-if="logoutError" role="alert" class="notice error">{{ logoutError }}</p>
    <RouterView :key="route.name + ':' + (route.params.id || '') + ':' + searchRevision" />
  </main>
</template>
