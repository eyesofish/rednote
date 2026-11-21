<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, UserRound } from '@lucide/vue'
import { login } from '../session'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const pending = ref(false)
const error = ref('')

async function submit() {
  if (pending.value) return
  pending.value = true
  error.value = ''
  try {
    await login(username.value.trim(), password.value)
    const next = String(route.query.next || '/')
    await router.replace(/^\/(?![/\\])/.test(next) && !next.startsWith('/login') ? next : '/')
  } catch (e) {
    error.value = e.status === 401 ? '账号或密码不正确' : '暂时无法登录，请重试'
  } finally {
    pending.value = false
  }
}
function selectDemo(name) {
  username.value = name
  password.value = 'notebook-demo'
  submit()
}
</script>

<template>
  <div class="auth-layout">
    <section class="form-panel login-panel">
      <img src="/mark.svg" width="44" height="44" alt="" />
      <h1>登录页间</h1>
      <form class="entry-form" @submit.prevent="submit">
        <label>用户名<input v-model="username" autocomplete="username" required maxlength="100" /></label>
        <label>密码<input v-model="password" autocomplete="current-password" type="password" required /></label>
        <p v-if="error" class="notice error" role="alert">{{ error }}</p>
        <button class="btn accent" :disabled="pending">{{ pending ? '正在登录…' : '登录' }}<ArrowRight :size="16" /></button>
      </form>
      <div class="demo-area">
        <p>使用示例账号</p>
        <div class="demo-buttons">
          <button v-for="name in ['lune', 'kai']" :key="name" class="btn secondary" :disabled="pending" @click="selectDemo(name)">
            <UserRound :size="15" />{{ name }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
