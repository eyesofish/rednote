import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'

// A self-contained two-pixel-wide PNG exercises the multipart upload and image reader.
const file = {
  name: 'notebook.png',
  mimeType: 'image/png',
  buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGPc7WrBwMDAxAAGAA9NATym/6x4AAAAAElFTkSuQmCC', 'base64'),
}

async function signIn(page, name) {
  await page.goto('/login')
  await page.getByRole('button', { name, exact: true }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}

test('两个真实会话走通发帖、权限、收藏、编辑、删除和退出', async ({ page, browser, baseURL }) => {
  const reader = await browser.newContext({ baseURL })
  const readerPage = await reader.newPage()
  const title = '浏览器验收 ' + randomUUID()
  let noteUrl
  try {
    await signIn(page, 'lune')
    await signIn(readerPage, 'kai')
    await page.getByRole('link', { name: '写笔记' }).click()
    await page.getByLabel('选择笔记图片').setInputFiles(file)
    await page.getByLabel('标题', { exact: true }).fill(title)
    await page.getByLabel('正文', { exact: true }).fill('给另一位读者的独立验收笔记。')
    await page.getByRole('button', { name: '发布笔记' }).click()
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
    noteUrl = new URL(page.url()).pathname

    await readerPage.goto('/')
    await readerPage.getByRole('link', { name: title, exact: true }).click()
    await expect(readerPage.getByRole('link', { name: '编辑', exact: true })).toHaveCount(0)
    await readerPage.getByRole('button', { name: '收藏笔记' }).click()
    await readerPage.getByRole('link', { name: '我的收藏' }).click()
    await readerPage.getByRole('link', { name: title, exact: true }).click()
    await readerPage.getByRole('button', { name: '取消收藏' }).click()
    await expect(readerPage.getByRole('button', { name: '收藏笔记' })).toBeVisible()

    await page.getByRole('link', { name: '编辑', exact: true }).click()
    await page.getByLabel('标题', { exact: true }).fill(title + ' 改')
    await page.getByRole('button', { name: '保存修改' }).click()
    await expect(page.getByRole('heading', { name: title + ' 改' })).toBeVisible()
    await readerPage.reload()
    await expect(readerPage.getByRole('heading', { name: title + ' 改' })).toBeVisible()
    await page.getByRole('button', { name: '删除笔记' }).click()
    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(page.getByRole('heading', { name: '发现笔记' })).toBeVisible()
    await readerPage.reload()
    await expect(readerPage.getByRole('alert')).toContainText('这篇笔记已不存在')
    noteUrl = undefined
    await page.getByRole('button', { name: '退出登录' }).click()
    await expect(page.getByRole('link', { name: '登录', exact: true })).toBeVisible()
  } finally {
    if (noteUrl) await page.request.delete('/api' + noteUrl)
    await reader.close()
  }
})

test('从真实搜索结果打开标题命中的示例笔记', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('searchbox').fill('美团')
  await page.getByRole('searchbox').press('Enter')
  const cards = page.locator('.card-link')
  await expect(cards.first()).toContainText('美团一面复盘')
  await expect(cards).toContainText(['美团一面复盘', '周末面试笔记'])
  await cards.first().click()
  await expect(page.getByRole('heading', { name: '美团一面复盘' })).toBeVisible()
})
