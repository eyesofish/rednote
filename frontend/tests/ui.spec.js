import { expect, test } from '@playwright/test'

const cards = [
  { id: 1, title: '美团一面复盘', cover_url: '/mark.svg', author_name: '阿月', published_at: '2026-01-20T09:30:00Z' },
  { id: 2, title: '周末面试笔记', cover_url: '/mark.svg', author_name: '小凯', published_at: '2026-01-19T09:30:00Z' },
]

test.beforeEach(async ({ page }) => {
  await page.route('**/api/me', route => route.fulfill({ status: 401, json: {} }))
  await page.route('**/api/notes', route => route.fulfill({ json: { items: cards } }))
})

test('搜索故障与正常零结果分别提示，重试后恢复', async ({ page }) => {
  let unavailable = false
  await page.route('**/api/search?*', route => route.fulfill(unavailable
    ? { status: 503, json: { code: 'SEARCH_UNAVAILABLE' } }
    : { json: { items: [] } }))
  await page.goto('/')
  await page.getByRole('searchbox').fill('火山')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.getByText('没有找到相关笔记')).toBeVisible()
  unavailable = true
  await page.getByRole('searchbox').press('Enter')
  await expect(page.getByRole('alert')).toHaveText(/搜索暂时不可用，请稍后再试/)
  await expect(page.getByText('没有找到相关笔记')).toHaveCount(0)
  unavailable = false
  await page.getByRole('button', { name: '重试' }).click()
  await expect(page.getByText('没有找到相关笔记')).toBeVisible()
})

test('窄屏能浏览双列卡片、导航和搜索', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '发现笔记' })).toBeVisible()
  const links = page.locator('.card-cover')
  const first = await links.nth(0).boundingBox()
  const second = await links.nth(1).boundingBox()
  expect(first.y).toBe(second.y)
  expect(first.x).toBeLessThan(second.x)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360)
  await page.getByRole('link', { name: '我的收藏' }).click()
  await expect(page.getByRole('heading', { name: '登录页间' })).toBeVisible()
  await expect(page).toHaveURL(/next=.*favorites/)
})
