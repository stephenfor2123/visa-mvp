/**
 * Simple SPA static server with fallback to index.html for all routes.
 * Used for screenshot capture (avoids vite preview cache bug).
 */
import http from 'node:http'
import fs from 'node:fs/promises'
import path from 'node:path'

const DIST = '/Users/stephen/Desktop/签证项目/frontend/web/dist'
const PORT = 4174

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
}

async function serve(req, res) {
  // Strip query string
  const url = new URL(req.url, `http://localhost:${PORT}`)
  let filePath = path.join(DIST, url.pathname)

  try {
    const stat = await fs.stat(filePath)
    if (stat.isDirectory()) {
      filePath = path.join(filePath, 'index.html')
    }
    const ext = path.extname(filePath)
    const mime = MIME[ext] || 'application/octet-stream'
    const data = await fs.readFile(filePath)
    res.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'no-cache' })
    res.end(data)
  } catch {
    // SPA fallback: serve index.html for all non-asset paths
    const ext = path.extname(url.pathname)
    if (ext === '' || ext === '.html') {
      try {
        const data = await fs.readFile(path.join(DIST, 'index.html'))
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' })
        res.end(data)
      } catch {
        res.writeHead(500)
        res.end('index.html not found')
      }
    } else {
      res.writeHead(404)
      res.end('Not found')
    }
  }
}

const server = http.createServer(serve)
server.listen(PORT, () => console.log(`SPA server on ${PORT}`))