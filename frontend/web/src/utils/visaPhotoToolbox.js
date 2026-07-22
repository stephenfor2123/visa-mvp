/**
 * Visa ID-photo toolbox — face-centered crop + white background.
 * Ported from prototypes/visa-photo-crop-preview.html
 */

export const PHOTO_SPECS = {
  US: {
    id: 'US',
    labelKey: 'wizard.photo_toolbox.spec_us',
    mmW: 51,
    mmH: 51,
    pxW: 600,
    pxH: 600,
  },
  SCHENGEN: {
    id: 'SCHENGEN',
    labelKey: 'wizard.photo_toolbox.spec_schengen',
    mmW: 35,
    mmH: 45,
    pxW: 413,
    pxH: 531,
  },
  GB: {
    id: 'GB',
    labelKey: 'wizard.photo_toolbox.spec_gb',
    mmW: 35,
    mmH: 45,
    pxW: 413,
    pxH: 531,
  },
  AU: {
    id: 'AU',
    labelKey: 'wizard.photo_toolbox.spec_au',
    mmW: 35,
    mmH: 40,
    pxW: 413,
    pxH: 472,
  },
}

const SCHENGEN_CODES = new Set([
  'AT', 'BE', 'HR', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
  'HU', 'IS', 'IT', 'LV', 'LI', 'LT', 'LU', 'MT', 'NL', 'NO',
  'PL', 'PT', 'SK', 'SI', 'ES', 'SE', 'CH',
])

export function resolvePhotoSpec(countryCode) {
  const cc = String(countryCode || '').trim().toUpperCase()
  if (cc === 'UK') return PHOTO_SPECS.GB
  if (PHOTO_SPECS[cc]) return PHOTO_SPECS[cc]
  if (SCHENGEN_CODES.has(cc)) return PHOTO_SPECS.SCHENGEN
  return PHOTO_SPECS.US
}

export function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('image_load_failed'))
    }
    img.src = url
  })
}

export async function detectFaceBox(img) {
  if (typeof window !== 'undefined' && 'FaceDetector' in window) {
    try {
      const detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
      const faces = await detector.detect(img)
      if (faces[0]) {
        const b = faces[0].boundingBox
        return { x: b.x, y: b.y, w: b.width, h: b.height }
      }
    } catch {
      /* fallback below */
    }
  }
  const w = img.naturalWidth || img.width
  const h = img.naturalHeight || img.height
  return { x: w * 0.28, y: h * 0.12, w: w * 0.44, h: h * 0.42 }
}

function sampleBg(img) {
  const c = document.createElement('canvas')
  const w = Math.min(100, img.naturalWidth || img.width)
  const h = Math.min(100, img.naturalHeight || img.height)
  c.width = w
  c.height = h
  const g = c.getContext('2d', { willReadFrequently: true })
  g.drawImage(img, 0, 0, w, h)
  const pts = [[2, 2], [w - 3, 2], [2, h - 3], [w - 3, h - 3], [w / 2, 2]]
  let r = 0
  let gc = 0
  let b = 0
  pts.forEach(([x, y]) => {
    const d = g.getImageData(x | 0, y | 0, 1, 1).data
    r += d[0]
    gc += d[1]
    b += d[2]
  })
  return [r / pts.length, gc / pts.length, b / pts.length]
}

function colorDist(a, b) {
  const dr = a[0] - b[0]
  const dg = a[1] - b[1]
  const db = a[2] - b[2]
  return Math.sqrt(dr * dr + dg * dg + db * db)
}

/**
 * Draw face-centered crop + soft white background onto canvas.
 * @returns {{ pxW: number, pxH: number, mmW: number, mmH: number }}
 */
export async function renderVisaPhoto(canvas, img, spec, { zoom = 1.08, offX = 0, offY = -6 } = {}) {
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  canvas.width = spec.pxW
  canvas.height = spec.pxH

  const face = await detectFaceBox(img)
  const faceCx = face.x + face.w / 2
  const faceCy = face.y + face.h * 0.42
  const targetFaceW = spec.pxW * (spec.mmW === spec.mmH ? 0.58 : 0.52)
  const scale = (targetFaceW / Math.max(face.w, 1)) * zoom
  const iw = img.naturalWidth || img.width
  const ih = img.naturalHeight || img.height
  const sx = faceCx - (spec.pxW / 2) / scale + (offX / 100) * iw
  const sy = faceCy - (spec.pxH * 0.38) / scale + (offY / 100) * ih

  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, spec.pxW, spec.pxH)

  const tmp = document.createElement('canvas')
  tmp.width = spec.pxW
  tmp.height = spec.pxH
  const tctx = tmp.getContext('2d', { willReadFrequently: true })
  tctx.drawImage(img, sx, sy, spec.pxW / scale, spec.pxH / scale, 0, 0, spec.pxW, spec.pxH)

  const bg = sampleBg(img)
  const src = tctx.getImageData(0, 0, spec.pxW, spec.pxH)
  const dst = ctx.getImageData(0, 0, spec.pxW, spec.pxH)
  const thresh = 52
  for (let i = 0; i < src.data.length; i += 4) {
    const px = [src.data[i], src.data[i + 1], src.data[i + 2]]
    const d = colorDist(px, bg)
    const luma = 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]
    const nearWhite = luma > 210 && Math.abs(px[0] - px[1]) < 18 && Math.abs(px[1] - px[2]) < 18
    if (d < thresh || nearWhite) {
      const a = nearWhite ? 1 : Math.min(1, (thresh - d) / thresh)
      dst.data[i] = Math.round(px[0] * (1 - a) + 255 * a)
      dst.data[i + 1] = Math.round(px[1] * (1 - a) + 255 * a)
      dst.data[i + 2] = Math.round(px[2] * (1 - a) + 255 * a)
      dst.data[i + 3] = 255
    } else {
      dst.data[i] = px[0]
      dst.data[i + 1] = px[1]
      dst.data[i + 2] = px[2]
      dst.data[i + 3] = 255
    }
  }
  ctx.putImageData(dst, 0, 0)
  return { pxW: spec.pxW, pxH: spec.pxH, mmW: spec.mmW, mmH: spec.mmH }
}

export function canvasToJpegFile(canvas, filename = 'photo_htex_cropped.jpg', quality = 0.92) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('canvas_to_blob_failed'))
        return
      }
      resolve(new File([blob], filename, { type: 'image/jpeg' }))
    }, 'image/jpeg', quality)
  })
}
