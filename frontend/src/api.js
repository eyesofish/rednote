export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export async function request(path, { json, ...options } = {}) {
  if (json !== undefined) {
    options.headers = { ...options.headers, 'Content-Type': 'application/json' }
    options.body = JSON.stringify(json)
  }
  const response = await fetch('/api' + path, { credentials: 'same-origin', ...options })
  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message = typeof data?.detail === 'string' ? data.detail : ''
    throw new ApiError(response.status, message)
  }
  return data
}

export function readableError(error, fallback = '暂时无法完成操作，请重试') {
  if (error.status === 401) return '请登录后再试'
  if (error.status === 403) return '只有作者可以修改这篇笔记'
  if (error.status === 404) return '这篇笔记已不存在'
  if ([400, 413, 415, 422].includes(error.status)) return '请检查填写内容及图片格式和大小'
  return fallback
}

export function publishedDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(date).replaceAll('/', '.')
}
