import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Feed from './pages/Feed.vue'
import Editor from './pages/Editor.vue'
import Detail from './pages/Detail.vue'
import Login from './pages/Login.vue'
import { loadSession, user } from './session'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Feed, meta: { title: '发现笔记' } },
    { path: '/search', name: 'search', component: Feed, meta: { title: '搜索笔记' } },
    { path: '/favorites', name: 'favorites', component: Feed, meta: { title: '我的收藏', auth: true } },
    { path: '/notes/new', name: 'create', component: Editor, meta: { title: '写笔记', auth: true } },
    { path: '/notes/:id(\\d+)', name: 'detail', component: Detail, meta: { title: '笔记详情' } },
    { path: '/notes/:id(\\d+)/edit', name: 'edit', component: Editor, meta: { title: '编辑笔记', auth: true } },
    { path: '/login', name: 'login', component: Login, meta: { title: '登录' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (_to, _from, position) => position || { top: 0 },
})

const initialSession = loadSession().catch(() => {})
router.beforeEach(async (to) => {
  await initialSession
  if (to.meta.auth && !user.value) return { name: 'login', query: { next: to.fullPath } }
  document.title = to.meta.title + ' · 页间'
})
createApp(App).use(router).mount('#app')
