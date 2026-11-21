import { ref } from 'vue'
import { request } from './api'

export const user = ref(null)
export async function loadSession() {
  try {
    user.value = await request('/me')
  } catch (error) {
    if (error.status !== 401) throw error
    user.value = null
  }
}

export async function login(username, password) {
  user.value = await request('/sessions', { method: 'POST', json: { username, password } })
}

export async function logout() {
  await request('/sessions/current', { method: 'DELETE' })
  user.value = null
}
