import {
  AlignmentType,
  Document,
  Packer,
  PageBreak,
  Paragraph,
  TextRun,
} from 'docx'
import { EMPLOYMENT_WORD_TEMPLATE } from '@/data/materialTemplates'

const FONT_BY_LANG = {
  zh: 'Microsoft YaHei',
  en: 'Arial',
  vi: 'Arial',
  id: 'Arial',
}

function templateParagraphs(template, lang, { pageBreak = false } = {}) {
  const font = FONT_BY_LANG[lang] || FONT_BY_LANG.en
  const children = []

  if (pageBreak) {
    children.push(new Paragraph({ children: [new PageBreak()] }))
  }
  if (template.headerNote) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 180 },
      children: [new TextRun({ text: template.headerNote, italics: true, size: 20, font })],
    }))
  }
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 320 },
    children: [new TextRun({ text: template.title, bold: true, size: 30, font })],
  }))

  for (const line of template.body || []) {
    children.push(new Paragraph({
      spacing: { after: line ? 120 : 80, line: 360 },
      indent: line ? { firstLine: 420 } : undefined,
      children: [new TextRun({ text: line || ' ', size: 22, font })],
    }))
  }

  children.push(new Paragraph({ spacing: { before: 280 } }))
  for (const line of template.signature || []) {
    children.push(new Paragraph({
      alignment: AlignmentType.RIGHT,
      spacing: { after: 80 },
      children: [new TextRun({ text: line || ' ', size: 22, font })],
    }))
  }
  return children
}

function normalizedLang(locale) {
  const value = String(locale || '').toLowerCase()
  if (value.startsWith('zh')) return 'zh'
  if (value.startsWith('vi')) return 'vi'
  if (value.startsWith('id')) return 'id'
  return 'en'
}

/**
 * Generate the employment certificate shown in the preview as an editable
 * .docx file. Non-English locales include the local template followed by the
 * English reference on a new page.
 */
export async function exportEmploymentWord(locale) {
  const lang = normalizedLang(locale)
  const templates = EMPLOYMENT_WORD_TEMPLATE.templates
  const localTemplate = templates[lang] || templates.en
  const paragraphs = templateParagraphs(localTemplate, lang)

  if (lang !== 'en') {
    paragraphs.push(...templateParagraphs(templates.en, 'en', { pageBreak: true }))
  }

  const document = new Document({
    sections: [{
      properties: {
        page: {
          margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
        },
      },
      children: paragraphs,
    }],
  })
  const blob = await Packer.toBlob(document)
  const url = URL.createObjectURL(blob)
  const link = documentElement('a')
  link.href = url
  link.download = `employment-certificate-${lang}.docx`
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function documentElement(tag) {
  return window.document.createElement(tag)
}
