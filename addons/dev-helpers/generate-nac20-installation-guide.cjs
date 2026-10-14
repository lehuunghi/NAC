#!/usr/bin/env node
// Keep the pre-installation Markdown identical to the in-product instructions.
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const root = path.resolve(__dirname, '../..')
const sourcePath = path.join(root, 'html/pfappserver/root/src/views/Status/about/_config/installation.js')
const targetPath = path.join(root, 'docs/NAC20_CAI_DAT.md')
const source = fs.readFileSync(sourcePath, 'utf8').replace('export const installation =', 'const installation =')
const guide = vm.runInNewContext(`${source}\ninstallation`, {}, { timeout: 1000 })
const output = [
  '<!-- Generated from the About page content. Run node addons/dev-helpers/generate-nac20-installation-guide.cjs to update. -->',
  `# ${guide.title}`,
  '**NAC20 · Công Ty TNHH TN20 · 20.com.vn**',
  guide.subtitle,
  `> **Chuẩn bị bộ cài trước khi bắt đầu:** ${guide.packageNotice}`,
  guide.commandNotice,
  '## Mô hình triển khai',
  guide.architecture.join(' → '),
  '## Yêu cầu hệ thống'
]

function facts (rows) {
  output.push([
    '| Hạng mục | Nội dung |',
    '|---|---|',
    ...rows.map(row => `| ${row.name} | ${row.value.replace(/\|/g, '\\|')} |`)
  ].join('\n'))
}

function commands (blocks) {
  for (const block of blocks || []) {
    output.push(`**${block.label}**`, `\`\`\`bash\n${block.code}\n\`\`\``)
  }
}

facts(guide.requirements)
output.push('## Địa chỉ ví dụ')
facts(guide.addresses)
output.push('## Các cổng mạng')
facts(guide.ports)
for (const [index, step] of guide.steps.entries()) {
  output.push(`## ${index + 1}. ${step.title}`, step.summary, ...(step.paragraphs || []))
  commands(step.codeBlocks)
  if (step.items) output.push(step.items.map((item, i) => `${i + 1}. ${item}`).join('\n'))
  commands(step.codeBlocksAfter)
  output.push(`**Kết quả cần đạt:** ${step.expected}`)
}
output.push('## Kiểm tra khi gặp lỗi')
facts(guide.troubleshooting)
const markdown = output.join('\n\n').trim() + '\n'
if (process.argv.includes('--check')) {
  if (!fs.existsSync(targetPath) || fs.readFileSync(targetPath, 'utf8').replace(/\r\n/g, '\n') !== markdown) {
    console.error('Installation Markdown differs from the About page. Regenerate it before committing.')
    process.exitCode = 1
  } else console.log('PASS: installation Markdown matches the About page.')
} else {
  fs.writeFileSync(targetPath, markdown, 'utf8')
  console.log('Updated docs/NAC20_CAI_DAT.md')
}
