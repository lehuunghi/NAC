<template>
  <section class="installation" aria-labelledby="nac20-install-title">
    <header class="installation-heading">
      <span class="installation-eyebrow">TRIỂN KHAI VÀ KẾT NỐI</span>
      <h2 id="nac20-install-title">{{ installation.title }}</h2>
      <p>{{ installation.subtitle }}</p>
    </header>

    <div class="installation-notice">
      <strong>Chuẩn bị bộ cài trước khi bắt đầu</strong>
      <p>{{ installation.packageNotice }}</p>
    </div>

    <ol class="installation-architecture" aria-label="Luồng kết nối NAC20">
      <li v-for="(node, index) in installation.architecture" :key="node">
        <span>{{ String(index + 1).padStart(2, '0') }}</span>{{ node }}
      </li>
    </ol>

    <div class="installation-layout">
      <nav class="installation-nav" aria-label="Các bước cài đặt NAC20">
        <h3>Nội dung cài đặt</h3>
        <a v-for="(step, index) in installation.steps" :key="step.id"
          :href="`#nac20-install-${step.id}`" @click.prevent="openStep(step.id)">
          <span>{{ index + 1 }}</span>{{ step.title }}
        </a>
      </nav>

      <div class="installation-content">
        <section class="installation-prerequisites" aria-labelledby="nac20-install-requirements">
          <h3 id="nac20-install-requirements">Yêu cầu và thông số cần chuẩn bị</h3>
          <dl class="installation-facts">
            <div v-for="row in installation.requirements" :key="row.name"><dt>{{ row.name }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
          <h4>Sơ đồ địa chỉ ví dụ</h4>
          <dl class="installation-facts">
            <div v-for="row in installation.addresses" :key="row.name"><dt>{{ row.name }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
          <h4>Các cổng mạng cần đối chiếu</h4>
          <dl class="installation-facts">
            <div v-for="row in installation.ports" :key="row.name"><dt>{{ row.name }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
          <p class="installation-command-note">{{ installation.commandNotice }}</p>
        </section>

        <details v-for="(step, index) in installation.steps" :id="`nac20-install-${step.id}`"
          :key="step.id" :open="index === 0" class="installation-step">
          <summary><span class="installation-step-number">{{ index + 1 }}</span><h3>{{ step.title }}</h3></summary>
          <div class="installation-step-body">
            <p class="installation-summary">{{ step.summary }}</p>
            <p v-for="paragraph in step.paragraphs" :key="paragraph">{{ paragraph }}</p>
            <div v-for="block in step.codeBlocks" :key="block.label" class="installation-code">
              <div class="installation-code-label">{{ block.label }}</div>
              <pre tabindex="0" :aria-label="block.label"><code>{{ block.code }}</code></pre>
            </div>
            <ol v-if="step.items && step.items.length" class="installation-instructions">
              <li v-for="item in step.items" :key="item">{{ item }}</li>
            </ol>
            <div v-for="block in step.codeBlocksAfter" :key="block.label" class="installation-code">
              <div class="installation-code-label">{{ block.label }}</div>
              <pre tabindex="0" :aria-label="block.label"><code>{{ block.code }}</code></pre>
            </div>
            <div class="installation-result"><strong>Kết quả cần đạt</strong><p>{{ step.expected }}</p></div>
          </div>
        </details>

        <section class="installation-troubleshooting" aria-labelledby="nac20-install-troubleshooting">
          <h3 id="nac20-install-troubleshooting">Kiểm tra khi gặp lỗi</h3>
          <dl class="installation-facts">
            <div v-for="row in installation.troubleshooting" :key="row.name"><dt>{{ row.name }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
        </section>
      </div>
    </div>
  </section>
</template>

<script>
import { installation } from '../_config/installation'

export default {
  name: 'nac20-installation-guide',
  data: () => ({ installation }),
  methods: {
    openStep (id) {
      const step = this.$el.querySelector(`#nac20-install-${id}`)
      if (!step) return
      step.open = true
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      step.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
    }
  }
}
</script>

<style lang="scss" scoped>
.installation { margin: 1rem 0 2.5rem; padding-top: 2rem; border-top: 1px solid #dce5ed; color: #40556b; }
.installation-eyebrow { font-size: .7rem; font-weight: 700; letter-spacing: .12em; color: #178579; }
.installation-heading h2 { margin: .5rem 0 .75rem; font-size: 1.65rem; letter-spacing: -.025em; color: #10243d; }
.installation-heading p { max-width: 750px; line-height: 1.7; }
.installation-notice { padding: 1.25rem 1.5rem; border: 1px solid #e6d5a1; border-left: 4px solid #b88b28; border-radius: 10px; background: #fffbef; color: #624b1b; line-height: 1.7; }
.installation-notice p { margin: .35rem 0 0; }
.installation-architecture { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); list-style: none; padding: 0; margin: 1.5rem 0 2rem; gap: .75rem; }
.installation-architecture li { display: flex; gap: .7rem; align-items: center; background: #e8f3f2; border: 1px solid #cde4e0; border-radius: 9px; padding: 1rem; font-size: .8rem; font-weight: 600; color: #185d56; }
.installation-architecture span { color: #548e86; font-size: .7rem; }
.installation-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 1.5rem; align-items: start; }
.installation-nav { position: sticky; top: 85px; padding: 1.25rem .75rem; border-radius: 12px; border: 1px solid #dfe7ef; background: white; }
.installation-nav h3 { font-size: .85rem; padding: 0 .5rem .75rem; margin: 0; color: #10243d; }
.installation-nav a { display: flex; align-items: baseline; gap: .65rem; padding: .65rem .5rem; line-height: 1.5; font-size: .8rem; color: #40556b; border-radius: 6px; }
.installation-nav a:hover, .installation-nav a:focus { background: #eef8f6; color: #0b7266; text-decoration: none; }
.installation-nav a span { min-width: 1rem; color: #178579; font-weight: 700; }
.installation-content { min-width: 0; }
.installation-prerequisites, .installation-troubleshooting { background: white; border: 1px solid #dfe7ef; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
.installation h3 { font-size: 1.05rem; color: #16344d; }
.installation h4 { font-size: .9rem; margin: 1.5rem 0 .75rem; color: #16344d; }
.installation-facts { margin: 1rem 0 0; }
.installation-facts > div { display: grid; grid-template-columns: minmax(130px, 1fr) 3fr; gap: 1rem; padding: .8rem 0; border-bottom: 1px solid #edf1f5; line-height: 1.7; font-size: .85rem; }
.installation-facts > div:last-child { border: 0; }
.installation-facts dt { font-weight: 600; }
.installation-facts dd { margin: 0; overflow-wrap: anywhere; }
.installation-command-note { font-size: .85rem; line-height: 1.7; margin: 1.25rem 0 0; padding: 1rem; background: #f3f6fa; border-radius: 8px; }
.installation-step { border: 1px solid #dfe7ef; border-radius: 12px; background: white; margin-bottom: 1rem; scroll-margin-top: 85px; }
.installation-step summary { padding: 1.1rem 1.25rem; cursor: pointer; color: #178579; }
.installation-step summary h3 { display: inline; font-size: .95rem; font-weight: 650; line-height: 1.6; }
.installation-step-number { display: inline-block; text-align: center; min-width: 1.7rem; margin: 0 .6rem; padding: .15rem; border-radius: 6px; color: #0b7266; background: #e8f3f2; font-weight: 700; font-size: .8rem; }
.installation-step[open] summary { border-bottom: 1px solid #edf1f5; }
.installation-step-body { padding: 1.5rem; font-size: .9rem; line-height: 1.8; }
.installation-summary { color: #0b7266; font-weight: 600; }
.installation-instructions { padding-left: 1.4rem; margin: 1.25rem 0; }
.installation-instructions li { padding-left: .3rem; margin-bottom: .75rem; }
.installation-code { min-width: 0; margin: 1.25rem 0; border-radius: 9px; overflow: hidden; border: 1px solid #253d52; }
.installation-code-label { background: #1e354a; color: #c2d9e5; padding: .6rem 1rem; font-size: .75rem; line-height: 1.6; }
.installation-code pre { margin: 0; padding: 1rem; overflow-x: auto; background: #10243d; color: #e0f1f3; font-size: .8rem; line-height: 1.8; tab-size: 2; }
.installation-code code { font-family: Consolas, "Liberation Mono", monospace; color: inherit; white-space: pre; }
.installation-result { padding: 1rem 1.25rem; border-radius: 8px; background: #eef8f6; border-left: 3px solid #178579; color: #205a51; }
.installation-result strong { font-size: .8rem; }
.installation-result p { margin: .25rem 0 0; font-size: .85rem; }
@media (max-width: 991px) { .installation-layout { grid-template-columns: minmax(0, 1fr); } .installation-nav { position: static; } .installation-nav a { display: inline-flex; max-width: 100%; margin-right: .5rem; } }
@media (max-width: 575px) { .installation-architecture { grid-template-columns: repeat(2, minmax(0, 1fr)); } .installation-facts > div { grid-template-columns: 1fr; gap: .25rem; } .installation-step-body, .installation-prerequisites, .installation-troubleshooting { padding: 1rem; } .installation-step summary { padding: 1rem .5rem; } .installation-notice { padding: 1rem; } }
@media print { .installation-nav { display: none; } .installation-layout { display: block; } .installation-step { break-inside: avoid; } }
</style>
