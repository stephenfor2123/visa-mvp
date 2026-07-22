// /api/v2/voice 前端 wrapper
//
// W14-5 语音录入端点 (V2 §3.3.3):
//   GET  /api/v2/voice/config                    - 查询支持语言和音频限制
//   POST /api/v2/voice/recognize                 - 上传音频 + 识别 + 提取字段
//
// 响应结构 (ApiResponse[dict]):
//   { name, address, travel_date, raw_text, lang, confidence, engine, mime_type, ... }
//   错误 code: 2003 VOICE_AUDIO_FORMAT / 2004 VOICE_RECOGNIZE_FAILED / 2005 VOICE_TIMEOUT

import http from './http'
import { isApiMockMode } from '@/utils/mockMode'

const MOCK_MODE = isApiMockMode()

function delay(ms = 400) {
  return new Promise((r) => setTimeout(r, ms))
}

// --------------------------------------------------------------------------- //
// mock 数据 (开发时绕过后端 ASR)                                               //
// --------------------------------------------------------------------------- //
const MOCK_TRANSCRIPTS = {
  'zh-CN': {
    name: '张三',
    address: '上海市浦东新区世纪大道100号',
    travel_date: '2026-08-15',
    raw_text: '我叫张三,护照号E12345678,2026年8月15日出发,地址是上海市浦东新区世纪大道100号',
  },
  en: {
    name: 'John Smith',
    address: '100 Main Street New York',
    travel_date: '2026-08-15',
    raw_text: 'My name is John Smith, passport A12345678, travel date 2026-08-15, I live at 100 Main Street New York',
  },
  id: {
    name: 'Andi',
    address: 'Jalan Sudirman nomor 100 Jakarta',
    travel_date: '2026-08-15',
    raw_text: 'Nama saya Andi, tinggal di Jalan Sudirman nomor 100 Jakarta, tanggal berangkat 2026-08-15',
  },
  vi: {
    name: 'Nguyễn Văn A',
    address: '100 Lê Lợi Quận 1 TP HCM',
    travel_date: '2026-08-15',
    raw_text: 'Tên tôi là Nguyễn Văn A, địa chỉ 100 Lê Lợi Quận 1 TP HCM, ngày khởi hành 2026-08-15',
  },
}

function genMockResult(lang = 'en') {
  const t = MOCK_TRANSCRIPTS[lang] || MOCK_TRANSCRIPTS.en
  return {
    name: t.name,
    address: t.address,
    travel_date: t.travel_date,
    raw_text: t.raw_text,
    lang,
    confidence: 0.93,
    engine: 'mock',
    mime_type: 'audio/webm',
    audio_bytes: 20480,
    elapsed_ms: 380,
  }
}

// --------------------------------------------------------------------------- //
// API 函数                                                                     //
// --------------------------------------------------------------------------- //

/**
 * GET /api/v2/voice/config
 * 查询支持语言列表 + 音频大小限制
 * @returns {Promise<{supported_langs: string[], min_audio_bytes: number, max_audio_bytes: number, active_engine: string}>}
 */
export async function getVoiceConfig() {
  if (MOCK_MODE) {
    await delay(120)
    return {
      supported_langs: ['zh-CN', 'en', 'id', 'vi'],
      min_audio_bytes: 1024,
      max_audio_bytes: 5242880,
      active_engine: 'mock',
    }
  }
  const resp = await http.get('/v2/voice/config')
  return resp.data
}

/**
 * POST /api/v2/voice/recognize
 * 上传音频文件,运行 ASR 并返回结构化字段.
 *
 * @param {Blob|File} audioFile - 录音生成的音频 Blob / File
 * @param {string} lang - 识别语言: zh-CN | en | id | vi
 * @param {function} [onUploadProgress] - 上传进度回调 (0-100)
 * @returns {Promise<{name: string|null, address: string|null, travel_date: string|null, raw_text: string, lang: string, confidence: number, engine: string}>}
 */
export async function recognize(audioFile, lang = 'en', onUploadProgress) {
  if (MOCK_MODE) {
    await delay(600)
    return genMockResult(lang)
  }

  const form = new FormData()
  form.append('file', audioFile, audioFile.name || 'recording.webm')
  form.append('lang', lang)

  const resp = await http.post('/v2/voice/recognize', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onUploadProgress
      ? (evt) => onUploadProgress(Math.round((evt.loaded / evt.total) * 100))
      : undefined,
  })
  return resp.data
}

/**
 * 轮询风格 getResult — 与 payment.js 保持一致的接口签名,
 * 用于 voice 场景下的语义等效封装.
 * (实际请求体已在 recognize() 完成,这里只做结果透传)
 *
 * @param {object} result - recognize() 返回的结构化结果
 * @returns {Promise<object>}
 */
export async function getResult(result) {
  // voice 识别是一次性同步完成,无需轮询;保留接口签名一致性
  if (MOCK_MODE) {
    await delay(80)
    return result
  }
  return result
}

/**
 * cancel — 语音识别不支持取消操作,保留接口签名.
 * 实际场景中如果用户录音中想中途停止,只需停止 MediaRecorder 即可.
 *
 * @param {string} [taskId] - 任务 ID (可选,语义占位)
 */
export async function cancel(taskId) {
  if (MOCK_MODE) {
    await delay(50)
  }
  // voice 识别是同步的,无法中途取消;调用方应停止 MediaRecorder
  return { cancelled: true, taskId }
}

// --------------------------------------------------------------------------- //
// VoiceRecorder.vue 依赖的别名/兼容导出                                       //
// --------------------------------------------------------------------------- //

/** getSupportedLangs — 与 VoiceRecorder.vue 的 langOptions computed 配合 */
export function getSupportedLangs() {
  if (MOCK_MODE) return ['zh-CN', 'en', 'id', 'vi']
  // 实际调用会在 getVoiceConfig() 后缓存;这里先返回默认值
  return ['zh-CN', 'en', 'id', 'vi']
}

/**
 * uploadAudio — VoiceRecorder.vue 的 onRecorderStop 调用入口.
 * 与 recognize() 是同一函数,保留别名便于语义命名.
 */
export const uploadAudio = recognize

/**
 * validateAudioFile — 前端本地校验音频大小.
 * @param {File|Blob} file
 * @throws {Error} 文件小于 1KB 或大于 5MB
 */
export function validateAudioFile(file) {
  const MIN = 1024
  const MAX = 5 * 1024 * 1024
  const size = file?.size || 0
  if (size < MIN) {
    throw Object.assign(new Error('Audio payload too small (<1 KB)'), { code: 'VOICE_AUDIO_FORMAT' })
  }
  if (size > MAX) {
    throw Object.assign(new Error('Audio payload too large (>5 MB)'), { code: 'VOICE_AUDIO_FORMAT' })
  }
}