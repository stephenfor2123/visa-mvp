// /api/v2/rpa 前端 wrapper
//
// W14 RPA 端点:
//   POST   /api/v2/rpa/submit              - 触发 RPA 提交 (body: { order_no })
//   GET    /api/v2/rpa/status/{taskId}     - 查询 RPA 任务状态
//   GET    /api/v2/rpa/config              - 获取 RPA 配置
//   PUT    /api/v2/rpa/config              - 更新 RPA 配置 (body: { enabled, retry_interval, ... })
//
// Mock 模式: VITE_MOCK !== 'false' 时使用本地 mock 数据

import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false'

function delay(ms = 300) {
  return new Promise((r) => setTimeout(r, ms))
}

// mock 任务状态流转: SUBMITTING -> WAITING -> DONE
// 模拟真实 RPA 流程: 访问官网 -> 填写表单 -> 提交申请
let MOCK_TASK_STATES = {}

function makeMockTask(orderNo) {
  const taskId = 'rpa_' + Math.random().toString(36).slice(2, 10)
  const task = {
    task_id: taskId,
    order_no: orderNo,
    status: 'SUBMITTING',
    phase: 'accessing', // accessing | filling | submitting
    step: 1,
    total_steps: 3,
    step_label_key: 'rpa.step_accessing',
    progress: 0,
    screenshots: [],
    error: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: null
  }
  MOCK_TASK_STATES[taskId] = task
  return task
}

function advanceMockTask(taskId) {
  const task = MOCK_TASK_STATES[taskId]
  if (!task) return null

  task.step += 1
  task.updated_at = new Date().toISOString()

  if (task.step === 2) {
    task.phase = 'filling'
    task.step_label_key = 'rpa.step_filling'
    task.progress = 40
  } else if (task.step === 3) {
    task.phase = 'submitting'
    task.step_label_key = 'rpa.step_submitting'
    task.progress = 75
    // 模拟截图
    task.screenshots = [
      `https://placehold.co/600x400/EAF0FE/2D5BFF?text=RPA+Submitting`,
      `https://placehold.co/600x400/FEF3C7/B45309?text=RPA+Filling`
    ]
  } else if (task.step > 3) {
    task.status = 'DONE'
    task.phase = 'done'
    task.step_label_key = 'rpa.step_done'
    task.progress = 100
    task.completed_at = new Date().toISOString()
    task.screenshots = [
      `https://placehold.co/600x400/DCFCE7/166534?text=RPA+DONE`
    ]
  }

  return task
}

/**
 * 触发 RPA 提交
 * @param {string} orderNo - 订单号
 * @returns {Promise<{task_id, order_no, status, created_at}>}
 */
export async function postRpaSubmit(orderNo) {
  if (!orderNo) throw new Error('orderNo is required')

  if (MOCK_MODE) {
    await delay()
    const task = makeMockTask(orderNo)
    // 启动后台轮询推进 mock 状态
    let steps = 0
    const interval = setInterval(() => {
      steps++
      const updated = advanceMockTask(task.task_id)
      if (!updated || updated.status === 'DONE') {
        clearInterval(interval)
      }
    }, 2000)
    return task
  }

  const env = await http.post('/v2/rpa/submit', { order_no: orderNo })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'RPA submit failed')
  }
  return env?.data || env
}

/**
 * 查询 RPA 任务状态
 * @param {string} taskId - 任务 ID
 * @returns {Promise<RpaTaskStatus>}
 */
export async function getRpaStatus(taskId) {
  if (!taskId) throw new Error('taskId is required')

  if (MOCK_MODE) {
    await delay(150)
    const task = MOCK_TASK_STATES[taskId]
    if (!task) {
      throw Object.assign(new Error('rpa.status_task_not_found'), { code: 'TASK_NOT_FOUND' })
    }
    return { ...task }
  }

  const env = await http.get(`/v2/rpa/status/${taskId}`)
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'get RPA status failed')
  }
  return env?.data || env
}

/**
 * 获取 RPA 配置
 * @returns {Promise<RpaConfig>}
 */
export async function getRpaConfig() {
  if (MOCK_MODE) {
    await delay(120)
    return {
      enabled: true,
      retry_interval: 1800,
      max_retries: 3,
      screenshot_interval: 5,
      timeout_seconds: 600
    }
  }

  const env = await http.get('/v2/rpa/config')
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'get RPA config failed')
  }
  return env?.data || env
}

/**
 * 更新 RPA 配置
 * @param {Partial<RpaConfig>} config
 * @returns {Promise<RpaConfig>}
 */
export async function updateRpaConfig(config) {
  if (!config || typeof config !== 'object') throw new Error('config must be an object')

  if (MOCK_MODE) {
    await delay(150)
    return { ...config }
  }

  const env = await http.put('/v2/rpa/config', config)
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'update RPA config failed')
  }
  return env?.data || env
}