import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dist = join(root, 'dist')
const origin = (process.env.VITE_SITE_URL || 'https://htexvisa.com').replace(/\/$/, '')
const updated = '2026-07-20'

const locales = {
  en: {
    lang: 'en',
    hrefLang: 'en',
    label: 'English',
    guides: 'Visa application guides',
    intro: 'Practical, source-linked guidance for preparing visitor visa applications. Requirements can change; always confirm with the relevant government authority.',
    requirements: 'Typical documents to prepare',
    steps: 'Application steps',
    facts: 'Key facts',
    sources: 'Official sources',
    disclaimer: 'Htex is a private visa application assistant, not a government agency. It cannot guarantee approval. The relevant government authority makes every visa decision.',
    updated: 'Last reviewed',
    cta: 'Check your documents with Htex',
    home: 'All visa guides',
  },
  vi: {
    lang: 'vi',
    hrefLang: 'vi',
    label: 'Tiếng Việt',
    guides: 'Hướng dẫn xin thị thực',
    intro: 'Hướng dẫn thực tế có liên kết nguồn chính thức để chuẩn bị hồ sơ thị thực du lịch. Quy định có thể thay đổi; luôn kiểm tra lại với cơ quan chính phủ liên quan.',
    requirements: 'Giấy tờ thường cần chuẩn bị',
    steps: 'Các bước nộp hồ sơ',
    facts: 'Thông tin chính',
    sources: 'Nguồn chính thức',
    disclaimer: 'Htex là dịch vụ hỗ trợ hồ sơ tư nhân, không phải cơ quan chính phủ và không thể bảo đảm được cấp thị thực. Cơ quan chính phủ liên quan quyết định mọi hồ sơ.',
    updated: 'Ngày kiểm tra gần nhất',
    cta: 'Kiểm tra hồ sơ với Htex',
    home: 'Tất cả hướng dẫn',
  },
  id: {
    lang: 'id',
    hrefLang: 'id',
    label: 'Bahasa Indonesia',
    guides: 'Panduan aplikasi visa',
    intro: 'Panduan praktis dengan tautan sumber resmi untuk menyiapkan aplikasi visa kunjungan. Persyaratan dapat berubah; selalu konfirmasikan kepada otoritas pemerintah terkait.',
    requirements: 'Dokumen yang umumnya perlu disiapkan',
    steps: 'Langkah aplikasi',
    facts: 'Fakta penting',
    sources: 'Sumber resmi',
    disclaimer: 'Htex adalah asisten aplikasi visa swasta, bukan lembaga pemerintah, dan tidak dapat menjamin persetujuan. Keputusan visa sepenuhnya dibuat oleh otoritas pemerintah terkait.',
    updated: 'Terakhir ditinjau',
    cta: 'Periksa dokumen dengan Htex',
    home: 'Semua panduan visa',
  },
  'zh-cn': {
    lang: 'zh-CN',
    hrefLang: 'zh-CN',
    label: '简体中文',
    guides: '签证申请指南',
    intro: '帮助准备访问签证材料的实用指南，并附官方来源。政策可能变化，请始终以相关政府部门最新要求为准。',
    requirements: '通常需要准备的材料',
    steps: '申请步骤',
    facts: '重要信息',
    sources: '官方来源',
    disclaimer: 'Htex 是私人签证申请辅助服务，不是政府机构，也不能保证获签。所有签证决定均由相关政府部门作出。',
    updated: '最后核验',
    cta: '使用 Htex 检查申请材料',
    home: '全部签证指南',
  },
}

const topics = [
  {
    slug: 'us-tourist-visa',
    official: [['U.S. visitor visa', 'https://travel.state.gov/content/travel/en/us-visas/tourism-visit/visitor.html'], ['DS-160', 'https://ceac.state.gov/genniv/']],
    copy: {
      en: ['US Tourist Visa (B-1/B-2): Documents and Application Steps', 'A B-1/B-2 visitor visa is generally used for temporary business, tourism or medical visits. Applicants normally complete DS-160, pay the government fee, schedule the required appointment and attend an interview.', ['Valid passport', 'DS-160 confirmation page', 'Appointment and fee receipt where applicable', 'Evidence of trip purpose and ability to pay', 'Evidence of circumstances and ties outside the United States'], ['Confirm the visitor visa category is appropriate', 'Complete and submit DS-160 accurately', 'Follow the embassy or consulate instructions for payment and appointment', 'Prepare supporting evidence and attend the interview']],
      vi: ['Visa du lịch Mỹ B-1/B-2: hồ sơ và các bước nộp', 'Visa B-1/B-2 thường dành cho chuyến đi công tác, du lịch hoặc điều trị y tế tạm thời. Đương đơn thường phải hoàn thành DS-160, nộp phí chính phủ, đặt lịch theo yêu cầu và tham dự phỏng vấn.', ['Hộ chiếu còn hiệu lực', 'Trang xác nhận DS-160', 'Xác nhận lịch hẹn và biên lai phí nếu áp dụng', 'Bằng chứng mục đích chuyến đi và khả năng chi trả', 'Bằng chứng về hoàn cảnh và ràng buộc ngoài Hoa Kỳ'], ['Xác nhận loại visa phù hợp', 'Điền và gửi DS-160 chính xác', 'Làm theo hướng dẫn thanh toán và đặt lịch của đại sứ quán/lãnh sự quán', 'Chuẩn bị bằng chứng hỗ trợ và tham dự phỏng vấn']],
      id: ['Visa Turis AS B-1/B-2: Dokumen dan Langkah Aplikasi', 'Visa pengunjung B-1/B-2 umumnya untuk kunjungan bisnis, wisata, atau perawatan medis sementara. Pemohon biasanya mengisi DS-160, membayar biaya pemerintah, membuat janji yang diwajibkan, dan menghadiri wawancara.', ['Paspor yang masih berlaku', 'Halaman konfirmasi DS-160', 'Konfirmasi janji dan bukti pembayaran jika berlaku', 'Bukti tujuan perjalanan dan kemampuan membayar', 'Bukti keadaan dan ikatan di luar Amerika Serikat'], ['Pastikan kategori visa pengunjung sesuai', 'Isi dan kirim DS-160 dengan akurat', 'Ikuti petunjuk pembayaran dan janji dari kedutaan/konsulat', 'Siapkan bukti pendukung dan hadiri wawancara']],
      'zh-cn': ['美国旅游签证 B-1/B-2：材料与申请步骤', 'B-1/B-2 访问签证通常适用于临时商务、旅游或医疗访问。申请人一般需要填写 DS-160、缴纳政府费用、按要求预约并参加面谈。', ['有效护照', 'DS-160 确认页', '适用时的预约确认和缴费凭证', '旅行目的及支付能力证明', '在美国境外的个人情况及约束力证明'], ['确认访问签证类别适用', '准确填写并提交 DS-160', '按使领馆要求缴费和预约', '准备支持材料并参加面谈']],
    },
  },
  {
    slug: 'uk-standard-visitor-visa',
    official: [['UK Standard Visitor visa', 'https://www.gov.uk/standard-visitor']],
    copy: {
      en: ['UK Standard Visitor Visa: Documents and Application Steps', 'The Standard Visitor route covers eligible tourism, family visits and certain business activities. Applicants apply online, prove that they are genuine visitors and show they can support the trip and leave at its end.', ['Valid passport or travel document', 'Evidence of permitted visit purpose', 'Evidence of funds and accommodation', 'Employment, study or personal circumstances', 'Certified translations for documents not in English or Welsh'], ['Check permitted activities and eligibility', 'Apply and pay online', 'Book and attend the biometrics appointment', 'Submit the requested supporting documents']],
      vi: ['Visa du lịch Anh Standard Visitor: hồ sơ và quy trình', 'Diện Standard Visitor áp dụng cho du lịch, thăm thân và một số hoạt động kinh doanh đủ điều kiện. Đương đơn nộp trực tuyến, chứng minh mục đích thăm viếng chân thực, có đủ khả năng chi trả và sẽ rời Anh khi kết thúc chuyến đi.', ['Hộ chiếu hoặc giấy thông hành còn hiệu lực', 'Bằng chứng mục đích chuyến đi được phép', 'Bằng chứng tài chính và chỗ ở', 'Bằng chứng việc làm, học tập hoặc hoàn cảnh cá nhân', 'Bản dịch chứng thực cho tài liệu không phải tiếng Anh hoặc tiếng Wales'], ['Kiểm tra hoạt động được phép và điều kiện', 'Nộp đơn và thanh toán trực tuyến', 'Đặt và tham dự lịch sinh trắc học', 'Nộp các tài liệu hỗ trợ được yêu cầu']],
      id: ['Visa UK Standard Visitor: Dokumen dan Proses Aplikasi', 'Rute Standard Visitor mencakup wisata, kunjungan keluarga, dan aktivitas bisnis tertentu yang memenuhi syarat. Pemohon mendaftar daring, membuktikan tujuan kunjungan yang sah, kemampuan membiayai perjalanan, dan niat meninggalkan Inggris setelah kunjungan.', ['Paspor atau dokumen perjalanan yang berlaku', 'Bukti tujuan kunjungan yang diizinkan', 'Bukti dana dan akomodasi', 'Bukti pekerjaan, studi, atau keadaan pribadi', 'Terjemahan tersertifikasi untuk dokumen selain bahasa Inggris atau Welsh'], ['Periksa aktivitas yang diizinkan dan kelayakan', 'Ajukan dan bayar secara daring', 'Buat dan hadiri janji biometrik', 'Kirim dokumen pendukung yang diminta']],
      'zh-cn': ['英国 Standard Visitor 访问签证：材料与流程', 'Standard Visitor 路线适用于符合条件的旅游、探亲和部分商务活动。申请人需要在线申请，证明访问目的真实、能够承担费用，并会在访问结束时离开英国。', ['有效护照或旅行证件', '获准访问目的的证明', '资金和住宿证明', '工作、学习或个人情况证明', '非英语或威尔士语材料的合格翻译件'], ['核对允许的活动和资格', '在线申请并付款', '预约并完成生物信息采集', '提交要求的支持材料']],
    },
  },
  {
    slug: 'schengen-short-stay-visa',
    official: [['European Commission — Schengen visa', 'https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/visa-policy_en']],
    copy: {
      en: ['Schengen Short-Stay Visa: Documents and Application Steps', 'A Schengen short-stay visa may permit visits of up to 90 days in any 180-day period. Apply through the competent country and check the responsible consulate or official application provider for local procedures.', ['Valid travel document', 'Completed application form and compliant photo', 'Travel medical insurance meeting current rules', 'Purpose, accommodation and itinerary evidence', 'Proof of sufficient means and intention to leave'], ['Identify the competent Schengen country', 'Check the responsible consulate’s local checklist', 'Book the appointment and provide biometrics if required', 'Submit documents and pay the applicable visa fee']],
      vi: ['Visa Schengen ngắn hạn: hồ sơ và các bước nộp', 'Visa Schengen ngắn hạn có thể cho phép lưu trú tối đa 90 ngày trong mỗi khoảng 180 ngày. Cần nộp cho quốc gia có thẩm quyền và kiểm tra quy trình địa phương của lãnh sự quán hoặc đơn vị tiếp nhận chính thức.', ['Giấy thông hành hợp lệ', 'Đơn đã hoàn thành và ảnh đúng chuẩn', 'Bảo hiểm y tế du lịch đáp ứng quy định hiện hành', 'Bằng chứng mục đích, chỗ ở và lịch trình', 'Bằng chứng đủ tài chính và ý định rời đi'], ['Xác định quốc gia Schengen có thẩm quyền', 'Kiểm tra danh sách hồ sơ của lãnh sự quán phụ trách', 'Đặt lịch và cung cấp sinh trắc học nếu được yêu cầu', 'Nộp hồ sơ và thanh toán lệ phí áp dụng']],
      id: ['Visa Schengen Jangka Pendek: Dokumen dan Langkah', 'Visa Schengen jangka pendek dapat mengizinkan kunjungan hingga 90 hari dalam periode 180 hari. Ajukan melalui negara yang berwenang dan periksa prosedur lokal konsulat atau penyedia aplikasi resmi.', ['Dokumen perjalanan yang berlaku', 'Formulir lengkap dan foto sesuai ketentuan', 'Asuransi medis perjalanan sesuai aturan terbaru', 'Bukti tujuan, akomodasi, dan rencana perjalanan', 'Bukti dana yang cukup dan niat untuk meninggalkan wilayah'], ['Tentukan negara Schengen yang berwenang', 'Periksa daftar dokumen konsulat yang bertanggung jawab', 'Buat janji dan berikan biometrik jika diwajibkan', 'Kirim dokumen dan bayar biaya visa yang berlaku']],
      'zh-cn': ['申根短期签证：材料与申请步骤', '申根短期签证通常允许在任意180天内停留不超过90天。应向有管辖权的国家申请，并查询对应使领馆或官方签证受理机构的当地流程。', ['有效旅行证件', '填写完整的申请表和合规照片', '符合现行要求的旅行医疗保险', '旅行目的、住宿和行程证明', '充足资金及按期离境证明'], ['确定有管辖权的申根国家', '查询负责使领馆的当地清单', '预约并按要求采集生物信息', '提交材料并缴纳适用签证费']],
    },
  },
  {
    slug: 'australia-visitor-visa',
    official: [['Australian Department of Home Affairs — Visitor visas', 'https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600']],
    copy: {
      en: ['Australia Visitor Visa (Subclass 600): Documents and Steps', 'Visitor visa subclass 600 has different streams. Applicants should select the appropriate stream, apply through the official system and provide evidence supporting the visit, finances and intention to comply with visa conditions.', ['Passport identity page', 'Purpose and itinerary evidence', 'Financial evidence', 'Employment, study, family or other circumstances', 'Translations where required'], ['Choose the appropriate Visitor visa stream', 'Create or use an ImmiAccount and apply online', 'Upload the requested evidence', 'Complete health, biometrics or other requests if issued']],
      vi: ['Visa du lịch Úc subclass 600: hồ sơ và các bước', 'Visa Visitor subclass 600 có nhiều diện. Đương đơn cần chọn đúng diện, nộp qua hệ thống chính thức và cung cấp bằng chứng về chuyến đi, tài chính và ý định tuân thủ điều kiện visa.', ['Trang thông tin hộ chiếu', 'Bằng chứng mục đích và lịch trình', 'Bằng chứng tài chính', 'Bằng chứng việc làm, học tập, gia đình hoặc hoàn cảnh khác', 'Bản dịch khi được yêu cầu'], ['Chọn đúng diện Visitor visa', 'Tạo hoặc sử dụng ImmiAccount và nộp trực tuyến', 'Tải lên bằng chứng được yêu cầu', 'Hoàn thành yêu cầu khám sức khỏe, sinh trắc học hoặc yêu cầu khác nếu có']],
      id: ['Visa Pengunjung Australia Subclass 600: Dokumen dan Langkah', 'Visitor visa subclass 600 memiliki beberapa stream. Pemohon harus memilih stream yang sesuai, mendaftar melalui sistem resmi, dan memberi bukti tujuan kunjungan, keuangan, serta niat mematuhi kondisi visa.', ['Halaman identitas paspor', 'Bukti tujuan dan rencana perjalanan', 'Bukti keuangan', 'Bukti pekerjaan, studi, keluarga, atau keadaan lain', 'Terjemahan bila diwajibkan'], ['Pilih stream Visitor visa yang sesuai', 'Buat atau gunakan ImmiAccount dan ajukan daring', 'Unggah bukti yang diminta', 'Penuhi permintaan kesehatan, biometrik, atau lainnya jika diterbitkan']],
      'zh-cn': ['澳大利亚访客签证 subclass 600：材料与步骤', 'Visitor visa subclass 600 包含不同类别。申请人应选择适用类别，通过官方系统申请，并提供支持访问目的、资金状况及遵守签证条件的证明。', ['护照身份信息页', '访问目的和行程证明', '资金证明', '工作、学习、家庭或其他个人情况证明', '按要求提供的翻译件'], ['选择适用的 Visitor visa 类别', '创建或使用 ImmiAccount 在线申请', '上传要求的证明材料', '收到要求时完成体检、生物信息或其他事项']],
    },
  },
  {
    slug: 'visa-bank-statement-guide',
    official: [['UK supporting documents guidance', 'https://www.gov.uk/government/publications/visitor-visa-guide-to-supporting-documents'], ['U.S. visitor visa', 'https://travel.state.gov/content/travel/en/us-visas/tourism-visit/visitor.html']],
    copy: {
      en: ['Bank Statements for Visa Applications: A Practical Guide', 'There is no universal bank-balance number that guarantees a visitor visa. Financial evidence should be genuine, consistent with the trip budget and explain the source of funds. Follow the exact checklist for your destination and application location.', ['Statements covering the period requested by the authority', 'Account holder name and account details', 'Regular income or a clear explanation of funds', 'Evidence explaining unusual large deposits', 'Sponsor evidence when another person pays'], ['Estimate a realistic trip budget', 'Use complete, unaltered statements', 'Match income and expenses to the rest of the application', 'Add a concise explanation and supporting proof for unusual transactions']],
      vi: ['Sao kê ngân hàng khi xin visa: hướng dẫn thực tế', 'Không có một số dư chung nào bảo đảm được cấp visa du lịch. Bằng chứng tài chính phải chân thực, phù hợp với ngân sách chuyến đi và giải thích được nguồn tiền. Hãy theo đúng danh sách của điểm đến và nơi nộp hồ sơ.', ['Sao kê trong khoảng thời gian cơ quan yêu cầu', 'Tên chủ tài khoản và thông tin tài khoản', 'Thu nhập đều đặn hoặc giải thích rõ nguồn tiền', 'Bằng chứng giải thích khoản nộp lớn bất thường', 'Bằng chứng của người bảo trợ nếu người khác chi trả'], ['Ước tính ngân sách chuyến đi thực tế', 'Dùng sao kê đầy đủ, không chỉnh sửa', 'Đảm bảo thu nhập và chi tiêu phù hợp với các phần khác của hồ sơ', 'Giải thích ngắn gọn và bổ sung bằng chứng cho giao dịch bất thường']],
      id: ['Rekening Koran untuk Aplikasi Visa: Panduan Praktis', 'Tidak ada angka saldo universal yang menjamin visa pengunjung disetujui. Bukti keuangan harus asli, sesuai anggaran perjalanan, dan menjelaskan sumber dana. Ikuti daftar resmi untuk tujuan dan lokasi aplikasi Anda.', ['Rekening koran untuk periode yang diminta otoritas', 'Nama pemilik dan detail rekening', 'Pendapatan rutin atau penjelasan sumber dana', 'Bukti yang menjelaskan setoran besar tidak biasa', 'Bukti sponsor bila perjalanan dibayar orang lain'], ['Hitung anggaran perjalanan yang realistis', 'Gunakan rekening koran lengkap tanpa perubahan', 'Selaraskan pemasukan dan pengeluaran dengan bagian aplikasi lain', 'Jelaskan transaksi tidak biasa dengan singkat dan lampirkan bukti']],
      'zh-cn': ['签证银行流水：实用准备指南', '不存在能够保证旅游签证获批的统一存款金额。资金证明应真实、与旅行预算相符，并能解释资金来源。请以目的地和申请地对应的官方清单为准。', ['覆盖官方要求期间的完整流水', '账户持有人姓名和账户信息', '稳定收入或清晰的资金来源说明', '解释异常大额入账的证明', '由他人承担费用时的资助人材料'], ['估算合理的旅行预算', '提交完整且未修改的流水', '确保收支情况与申请其他部分一致', '对异常交易作简短说明并附证明']],
    },
  },
]

const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
const pagePath = (locale, slug = '') => slug
  ? `/${locale}/visa-guides/${slug}/`
  : `/${locale}/visa-guides/`

function layout({ localeKey, title, description, path, body, schema, alternates }) {
  const l = locales[localeKey]
  const hreflang = Object.entries(alternates).map(([code, href]) => `<link rel="alternate" hreflang="${locales[code].hrefLang}" href="${href}">`).join('\n')
  return `<!doctype html>
<html lang="${l.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} · Htex</title>
<meta name="description" content="${esc(description)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="${origin}${path}">
${hreflang}
<link rel="alternate" hreflang="x-default" href="${alternates.en}">
<meta property="og:type" content="article"><meta property="og:site_name" content="Htex">
<meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${origin}${path}"><meta property="og:image" content="${origin}/icons/icon-512.png">
<script type="application/ld+json">${JSON.stringify(schema).replace(/</g, '\\u003c')}</script>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#f7f9fc}
*{box-sizing:border-box}body{margin:0}a{color:#245ce5}header,main,footer{max-width:920px;margin:auto;padding:24px}
header{display:flex;align-items:center;justify-content:space-between}header a{font-weight:750;text-decoration:none}.langs{display:flex;gap:12px;flex-wrap:wrap;font-size:14px}
main{background:#fff;border:1px solid #e4e9f2;border-radius:20px;box-shadow:0 12px 35px #1720330d;margin-bottom:32px;padding:clamp(24px,5vw,56px)}
h1{font-size:clamp(32px,5vw,50px);line-height:1.1;margin:0 0 18px}h2{font-size:24px;margin-top:38px}p,li{font-size:17px;line-height:1.75}
.lead{font-size:20px;color:#46536b}.meta,.notice{color:#5d6980}.notice{background:#f1f5ff;border-left:4px solid #3b6ef5;padding:16px;border-radius:8px}
.cta{display:inline-block;background:#245ce5;color:white;padding:13px 18px;border-radius:10px;text-decoration:none;font-weight:700;margin-top:20px}
footer{font-size:14px;color:#647087}@media(max-width:640px){header{align-items:flex-start;gap:16px;flex-direction:column}}
</style>
</head>
<body><header><a href="${origin}/home">Htex</a><nav class="langs" aria-label="Languages">${Object.entries(alternates).map(([code, href]) => `<a href="${href}" lang="${locales[code]?.lang || code}">${locales[code]?.label || code}</a>`).join('')}</nav></header>${body}<footer>© Htex · <a href="${origin}/agreement">Terms & privacy</a> · <a href="${origin}/llms.txt">AI site guide</a></footer></body></html>`
}

const sitemapPaths = ['/', '/home', '/destinations', '/schengen-countries', '/apply', '/diagnose', '/resources', '/resources/wiki', '/resources/policy', '/resources/templates', '/resources/faq', '/contact', '/pricing', '/agreement']

for (const [localeKey, l] of Object.entries(locales)) {
  const indexPath = pagePath(localeKey)
  const indexAlternates = Object.fromEntries(Object.keys(locales).map((key) => [key, `${origin}${pagePath(key)}`]))
  const cards = topics.map((topic) => {
    const [title, desc] = topic.copy[localeKey]
    return `<li><a href="${pagePath(localeKey, topic.slug)}"><strong>${esc(title)}</strong></a><br>${esc(desc)}</li>`
  }).join('')
  const indexBody = `<main><h1>${esc(l.guides)}</h1><p class="lead">${esc(l.intro)}</p><ul>${cards}</ul><p class="notice">${esc(l.disclaimer)}</p></main>`
  const indexSchema = { '@context': 'https://schema.org', '@type': 'CollectionPage', name: l.guides, description: l.intro, url: `${origin}${indexPath}`, inLanguage: l.lang, publisher: { '@type': 'Organization', name: 'Htex', url: origin } }
  const indexHtml = layout({ localeKey, title: l.guides, description: l.intro, path: indexPath, body: indexBody, schema: indexSchema, alternates: indexAlternates })
  const indexTarget = join(dist, localeKey, 'visa-guides', 'index.html')
  await mkdir(dirname(indexTarget), { recursive: true })
  await writeFile(indexTarget, indexHtml)
  sitemapPaths.push(indexPath)

  for (const topic of topics) {
    const [title, desc, docs, steps] = topic.copy[localeKey]
    const path = pagePath(localeKey, topic.slug)
    const alternates = Object.fromEntries(Object.keys(locales).map((key) => [key, `${origin}${pagePath(key, topic.slug)}`]))
    const body = `<main><p><a href="${pagePath(localeKey)}">← ${esc(l.home)}</a></p><article><h1>${esc(title)}</h1><p class="lead">${esc(desc)}</p><p class="meta">${esc(l.updated)}: ${updated}</p><h2>${esc(l.requirements)}</h2><ul>${docs.map((x) => `<li>${esc(x)}</li>`).join('')}</ul><h2>${esc(l.steps)}</h2><ol>${steps.map((x) => `<li>${esc(x)}</li>`).join('')}</ol><h2>${esc(l.sources)}</h2><ul>${topic.official.map(([name, url]) => `<li><a rel="noopener" href="${url}">${esc(name)}</a></li>`).join('')}</ul><p class="notice">${esc(l.disclaimer)}</p><a class="cta" href="${origin}/diagnose">${esc(l.cta)}</a></article></main>`
    const schema = { '@context': 'https://schema.org', '@type': 'Article', headline: title, description: desc, dateModified: updated, datePublished: updated, inLanguage: l.lang, mainEntityOfPage: `${origin}${path}`, author: { '@type': 'Organization', name: 'Htex' }, publisher: { '@type': 'Organization', name: 'Htex', url: origin, logo: { '@type': 'ImageObject', url: `${origin}/icons/icon-512.png` } }, citation: topic.official.map(([, url]) => url) }
    const html = layout({ localeKey, title, description: desc, path, body, schema, alternates })
    const target = join(dist, localeKey, 'visa-guides', topic.slug, 'index.html')
    await mkdir(dirname(target), { recursive: true })
    await writeFile(target, html)
    sitemapPaths.push(path)
  }
}

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${sitemapPaths.map((path) => `  <url><loc>${origin}${path}</loc><lastmod>${updated}</lastmod></url>`).join('\n')}
</urlset>
`
await writeFile(join(dist, 'sitemap.xml'), sitemap)
console.log(`generated ${Object.keys(locales).length * (topics.length + 1)} localized guide pages and ${sitemapPaths.length} sitemap URLs`)
