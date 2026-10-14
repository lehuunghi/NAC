<template>
  <div class="nac20-overview">
    <header class="nac20-hero">
      <div class="nac20-hero-copy">
        <span class="nac20-eyebrow">NỀN TẢNG KIỂM SOÁT TRUY CẬP MẠNG</span>
        <h1>NAC<span>20</span></h1>
        <p>Quản trị tập trung. Kết nối an toàn.</p>
        <div class="nac20-hero-meta"><span>Công Ty TNHH TN20</span><span>20.com.vn</span></div>
      </div>
      <div class="nac20-system-card">
        <span class="nac20-system-label">THÔNG TIN HỆ THỐNG</span>
        <dl><div><dt>Phiên bản</dt><dd>{{ version || '—' }}</dd></div>
          <div><dt>Máy chủ</dt><dd>{{ hostname || '—' }}</dd></div>
          <div><dt>Ngôn ngữ mặc định</dt><dd>Tiếng Việt</dd></div></dl>
      </div>
    </header>
    <main class="nac20-overview-body">
      <div class="nac20-section-heading">
        <div><span class="nac20-eyebrow">KHÔNG GIAN QUẢN TRỊ</span><h2>Điều hành hệ thống</h2></div>
        <b-input-group class="nac20-search">
          <b-input-group-prepend is-text><icon name="search" /></b-input-group-prepend>
          <b-form-input v-model="filter" type="search" placeholder="Tìm chức năng…" aria-label="Tìm chức năng quản trị" />
        </b-input-group>
      </div>
      <!-- Quick Links -->
      <template v-if="filteredSections.length">
        <h3 class="nac20-group-title">Truy cập nhanh</h3>
        <b-row class="mb-4">
          <b-col cols="12" sm="6" lg="4" xl="3" v-for="section in filteredSections" :key="section.path" class="mb-3">
          <div class="about-card-wrapper">
            <b-card class="about-card h-100 text-center" :to="section.path" tag="router-link">
              <icon :name="section.icon" scale="2" class="mb-2" />
              <div class="nac20-card-title">{{ section.name }}</div>
            </b-card>
            <div class="about-card-dropdown" v-if="section.items && section.items.length">
              <!-- Wrap each item group in a div for proper Vue tracking -->
              <div v-for="item in section.items" :key="item.path" class="about-card-dropdown-group">
                <router-link :to="item.path" class="about-card-dropdown-item">
                  {{ item.name }}
                </router-link>
                <!-- Saved searches for this specific item -->
                <router-link
                  v-for="search in item.savedSearches"
                  :key="`saved-${item.path}-${search.name}`"
                  :to="search.route"
                  class="about-card-dropdown-item about-card-dropdown-item-nested"
                >
                  <icon name="search" scale="0.8" class="mr-1" />
                  {{ search.name }}
                </router-link>
              </div>
            </div>
          </div>
        </b-col>
        </b-row>
      </template>

      <!-- Configuration -->
      <template v-if="filteredConfigSections.length">
        <h3 class="nac20-group-title">Cấu hình hệ thống</h3>
        <b-row class="mb-4">
          <b-col cols="12" sm="6" lg="4" xl="3" v-for="section in filteredConfigSections" :key="section.path" class="mb-3">
          <div class="about-card-wrapper">
            <b-card class="about-card h-100 text-center" :to="section.path" tag="router-link">
              <icon :name="section.icon" scale="2" class="mb-2" />
              <div class="nac20-card-title">{{ section.name }}</div>
            </b-card>
            <div class="about-card-dropdown" v-if="section.items && section.items.length">
              <div v-for="item in section.items" :key="item.path || item.name" class="about-card-dropdown-group">
                <template v-if="item.path">
                  <router-link :to="item.path" class="about-card-dropdown-item">
                    {{ item.name }}
                  </router-link>
                </template>
                <template v-else-if="item.items">
                  <div class="about-card-dropdown-header">{{ item.name }}</div>
                  <router-link
                    v-for="subitem in item.items"
                    :key="subitem.path"
                    :to="subitem.path"
                    class="about-card-dropdown-item about-card-dropdown-item-nested"
                  >
                    {{ subitem.name }}
                  </router-link>
                </template>
              </div>
            </div>
          </div>
          </b-col>
        </b-row>
      </template>

      <div v-if="!filteredSections.length && !filteredConfigSections.length" class="nac20-empty" role="status">
        <h3>Không tìm thấy chức năng</h3><p>Hãy thử từ khóa khác để tiếp tục.</p>
        <b-button variant="outline-primary" @click="filter = ''">Xóa bộ lọc</b-button>
      </div>
    </main>
    <footer class="nac20-footer"><strong>NAC20</strong><span>Công Ty TNHH TN20 · 20.com.vn</span></footer>
  </div>
</template>

<script>
import { computed, onMounted, ref, watch } from '@vue/composition-api'
import i18n from '@/utils/locale'
import { useSections as useConfigSections } from '@/views/Configuration/_composables/useSections'

const setup = (props, context) => {
  const { root: { $store, $router } = {} } = context

  // Helper to get saveSearchNamespace from router meta by path
  const getNamespaceFromRouter = (path) => {
    const routes = $router.options.routes || []
    // Recursively search for the route
    const findRoute = (routes, targetPath) => {
      for (const route of routes) {
        const fullPath = route.path
        if (fullPath === targetPath || `/${route.path}` === targetPath) {
          return route.meta?.saveSearchNamespace
        }
        if (route.children) {
          // Build child path
          for (const child of route.children) {
            const childPath = child.path.startsWith('/')
              ? child.path
              : `${fullPath}/${child.path}`.replace(/\/+/g, '/')
            if (childPath === targetPath) {
              return child.meta?.saveSearchNamespace
            }
          }
        }
      }
      return null
    }
    return findRoute(routes, path)
  }

  // System info from store
  const version = computed(() => $store.getters['system/version'])
  const isSaas = computed(() => $store.getters['system/isSaas'])

  const hostname = computed(() => $store.getters['system/hostname'])

  // Initialize preferences and load saved searches
  onMounted(() => {
    $store.dispatch('preferences/init')
  })

  // Reactive preferences cache (same pattern as SectionSidebarItem)
  const preferencesCache = ref({})
  watch(
    () => $store.state.preferences.cache,
    (newCache) => {
      preferencesCache.value = { ...newCache }
    },
    { deep: true, immediate: true }
  )

  // Helper to get saved searches for a namespace (used inside computed)
  const getSavedSearches = (cache, saveSearchNamespace, path) => {
    if (!saveSearchNamespace) return []

    const searches = []

    // Advanced searches
    const advancedKey = `${saveSearchNamespace}::advancedSearch`
    const { values: advancedValues = {} } = cache[advancedKey] || {}
    Object.keys(advancedValues).forEach(name => {
      const { query: conditionAdvanced } = advancedValues[name]
      if (conditionAdvanced) {
        searches.push({
          name,
          route: { path, query: { conditionAdvanced: JSON.stringify(conditionAdvanced) } }
        })
      }
    })

    // Basic searches
    const basicKey = `${saveSearchNamespace}::basicSearch`
    const { values: basicValues = {} } = cache[basicKey] || {}
    Object.keys(basicValues).forEach(name => {
      const { query: conditionBasic } = basicValues[name]
      if (conditionBasic) {
        searches.push({
          name,
          route: { path, query: { conditionBasic: JSON.stringify(conditionBasic) } }
        })
      }
    })

    return searches
  }

  // Quick link sections - savedSearches computed inline for reactivity
  const sections = computed(() => {
    const cache = preferencesCache.value

    // Raw section definitions
    const rawSections = [
      {
        name: i18n.t('Status'),
        path: '/status',
        icon: 'tachometer-alt',
        items: [
          { name: i18n.t('Dashboard'), path: isSaas.value ? '/status/dashboard_saas' : '/status/dashboard' },
          { name: i18n.t('Assets'), path: '/status/assets' },
          { name: i18n.t('Network Threats'), path: '/status/network_threats' },
          { name: i18n.t('Network Communication'), path: '/status/network_communication' },
          { name: i18n.t('Services'), path: isSaas.value ? '/status/services_saas' : '/status/services' },
          { name: i18n.t('Queue'), path: '/status/queue' }
        ]
      },
      {
        name: i18n.t('Reports'),
        path: '/reports',
        icon: 'chart-pie',
        items: []
      },
      {
        name: i18n.t('Auditing'),
        path: '/auditing',
        icon: 'clipboard-list',
        items: [
          { name: i18n.t('RADIUS Logs'), path: '/auditing/radiuslogs/search' },
          { name: i18n.t('DHCP Option 82'), path: '/auditing/dhcpoption82s/search' },
          { name: i18n.t('DNS Logs'), path: '/auditing/dnslogs/search' },
          { name: i18n.t('Admin API Logs'), path: '/auditing/admin_api_audit_logs/search' }
        ]
      },
      {
        name: i18n.t('Live Logs'),
        path: '/live-logs',
        icon: 'scroll',
        items: []
      },
      {
        name: i18n.t('Nodes'),
        path: '/nodes',
        icon: 'desktop',
        items: [
          { name: i18n.t('Search'), path: '/nodes/search' },
          { name: i18n.t('Create'), path: '/nodes/create' },
          { name: i18n.t('Import'), path: '/nodes/import' }
        ]
      },
      {
        name: i18n.t('Users'),
        path: '/users',
        icon: 'user',
        items: [
          { name: i18n.t('Search'), path: '/users/search' },
          { name: i18n.t('Create'), path: '/users/create' },
          { name: i18n.t('Import'), path: '/users/import' }
        ]
      }
    ]

    // Attach savedSearches to each item within the computed
    // Look up namespace from router meta
    return rawSections.map(section => ({
      ...section,
      items: (section.items || []).map(item => {
        const namespace = getNamespaceFromRouter(item.path)
        return {
          ...item,
          savedSearches: getSavedSearches(cache, namespace, item.path)
        }
      })
    }))
  })

  const { sections: configSections } = useConfigSections()

  // Keyword filter (persisted in Vuex store)
  const filter = computed({
    get: () => $store.state.$_status.aboutFilter,
    set: val => $store.commit('$_status/ABOUT_FILTER_UPDATED', val)
  })

  const matchesFilter = (text, keyword) => {
    return text.toLowerCase().includes(keyword)
  }

  // Filter items within a section, keeping only those that match.
  // Handles flat items (with path), grouped items (with nested items),
  // and saved searches.
  const filterItems = (items, keyword) => {
    return items.reduce((acc, item) => {
      // Flat item with path
      if (item.path) {
        if (matchesFilter(item.name, keyword)) {
          acc.push(item)
        } else {
          // Check saved searches
          const matchingSearches = (item.savedSearches || []).filter(s => matchesFilter(s.name, keyword))
          if (matchingSearches.length) {
            acc.push({ ...item, savedSearches: matchingSearches })
          }
        }
      }
      // Grouped item with nested sub-items (no path)
      else if (item.items) {
        if (matchesFilter(item.name, keyword)) {
          acc.push(item) // group header matches, keep all sub-items
        } else {
          const filteredSubs = item.items.filter(sub => matchesFilter(sub.name, keyword))
          if (filteredSubs.length) {
            acc.push({ ...item, items: filteredSubs })
          }
        }
      }
      return acc
    }, [])
  }

  // Filter sections, pruning dropdown items to only those matching.
  // If the section name itself matches, keep all its items.
  const filterSections = (allSections, keyword) => {
    return allSections.reduce((acc, section) => {
      if (matchesFilter(section.name, keyword)) {
        acc.push(section)
      } else {
        const items = filterItems(section.items || [], keyword)
        if (items.length) {
          acc.push({ ...section, items })
        }
      }
      return acc
    }, [])
  }

  const filteredSections = computed(() => {
    const keyword = filter.value.trim().toLowerCase()
    if (!keyword) return sections.value
    return filterSections(sections.value, keyword)
  })

  const filterSaas = (sections) => {
    if (!isSaas.value) return sections
    return sections.reduce((acc, section) => {
      if (section.class === 'no-saas') return acc
      const items = (section.items || []).reduce((itemAcc, item) => {
        if (item.class === 'no-saas') return itemAcc
        if (item.items) {
          const subItems = item.items.filter(sub => sub.class !== 'no-saas')
          if (subItems.length) {
            itemAcc.push({ ...item, items: subItems })
          }
        } else {
          itemAcc.push(item)
        }
        return itemAcc
      }, [])
      if (items.length || !section.items?.length) {
        acc.push({ ...section, items })
      }
      return acc
    }, [])
  }

  const filteredConfigSections = computed(() => {
    const sections = filterSaas(configSections.value)
    const keyword = filter.value.trim().toLowerCase()
    if (!keyword) return sections
    return filterSections(sections, keyword)
  })


  return {
    version,
    isSaas,
    filter,
    filteredSections,
    filteredConfigSections,
    hostname,
    sections,
    configSections
  }
}

// @vue/component
export default {
  name: 'the-view',
  setup
}
</script>

<style lang="scss" scoped>
.nac20-overview { max-width: 1600px; margin: 1.5rem auto; }
.nac20-hero { display: flex; gap: 2rem; align-items: center; justify-content: space-between; padding: 2.5rem 3rem; border-radius: 20px; color: #fff; background: radial-gradient(ellipse at top right, #1d5864 0, transparent 65%), #10243d; box-shadow: 0 12px 32px rgba(16,36,61,.12); }
.nac20-eyebrow { display: block; font-size: .7rem; font-weight: 700; letter-spacing: .14em; color: #688399; }
.nac20-hero .nac20-eyebrow { color: #93c8ca; }
.nac20-hero h1 { margin: .75rem 0; font-size: clamp(2.75rem, 5vw, 4rem); font-weight: 750; letter-spacing: -.06em; line-height: 1.1; }
.nac20-hero h1 span { color: #49d9ca; }
.nac20-hero p { color: #d8e3ec; font-size: 1.1rem; margin-bottom: 1.5rem; }
.nac20-hero-meta { display: flex; flex-wrap: wrap; gap: .6rem 1.25rem; font-size: .8rem; color: #aec6d7; }
.nac20-system-card { min-width: 285px; max-width: 100%; padding: 1.5rem; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.15); border-radius: 14px; }
.nac20-system-label { font-size: .65rem; letter-spacing: .12em; color: #a7cccf; font-weight: 700; }
.nac20-system-card dl { margin: 1rem 0 0; }
.nac20-system-card dl div { display: flex; justify-content: space-between; gap: 1.25rem; padding: .6rem 0; border-bottom: 1px solid rgba(255,255,255,.1); }
.nac20-system-card dl div:last-child { border: 0; padding-bottom: 0; }
.nac20-system-card dt { font-weight: 400; font-size: .8rem; color: #c6d6e1; }
.nac20-system-card dd { margin: 0; font-size: .8rem; font-weight: 600; text-align: right; overflow-wrap: anywhere; }
.nac20-overview-body { padding: 2.5rem .25rem .5rem; }
.nac20-section-heading { display: flex; gap: 1.5rem; align-items: center; justify-content: space-between; margin-bottom: 2rem; }
.nac20-section-heading h2 { font-size: 1.65rem; font-weight: 650; color: #10243d; margin: .45rem 0 0; letter-spacing: -.025em; }
.nac20-search { max-width: 340px; border: 1px solid #dce5ed; background: white; border-radius: 12px; overflow: hidden; }
.nac20-search ::v-deep .input-group-text { border: 0; background: white; color: #688399; padding-left: 1rem; }
.nac20-search ::v-deep .form-control { background: white; border: 0; min-height: 44px; }
.nac20-group-title { margin: 0 0 1rem; font-size: .95rem; font-weight: 650; color: #40556b; }
.about-card-wrapper { position: relative; height: 100%; }
.about-card { display: block; border: 1px solid #e0e8ef; border-radius: 14px; background: white; color: #16344d; box-shadow: 0 3px 12px rgba(16,36,61,.025); transition: border-color .18s, box-shadow .18s, transform .18s; }
.about-card ::v-deep .card-body { display: flex; align-items: center; gap: 1rem; text-align: left; padding: 1.35rem; }
.about-card ::v-deep .fa-icon { color: #178579; flex-shrink: 0; margin-bottom: 0 !important; width: 24px; height: 24px; }
.nac20-card-title { font-size: .9rem; font-weight: 600; line-height: 1.5; }
.about-card:hover, .about-card:focus { border-color: #22b8a8; box-shadow: 0 8px 24px rgba(16,36,61,.08); transform: translateY(-2px); text-decoration: none; }
.about-card:focus-visible { outline: 3px solid #22b8a8; outline-offset: 3px; }
.about-card-dropdown { display: none; position: absolute; top: calc(100% - 2px); left: 0; right: 0; z-index: 20; padding: .5rem; flex-direction: column; border: 1px solid #dce5ed; background: white; border-radius: 0 0 12px 12px; box-shadow: 0 12px 24px rgba(16,36,61,.12); }
.about-card-wrapper:hover .about-card-dropdown, .about-card-wrapper:focus-within .about-card-dropdown { display: flex; }
.about-card-dropdown-item { display: block; padding: .65rem .75rem; border-radius: 6px; color: #40556b; font-size: .8rem; }
.about-card-dropdown-item:hover, .about-card-dropdown-item:focus { background: #eef8f6; color: #0b7266; text-decoration: none; }
.about-card-dropdown-item-nested { padding-left: 1.5rem; }
.about-card-dropdown-header { padding: .6rem .75rem .25rem; font-size: .7rem; font-weight: 700; color: #688399; }
.nac20-footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: .75rem; padding: 1.5rem .25rem; border-top: 1px solid #dce5ed; color: #688399; font-size: .75rem; }
.nac20-footer strong { letter-spacing: .05em; color: #40556b; }
.nac20-empty { padding: 3rem 1rem; text-align: center; color: #688399; background: white; border-radius: 14px; margin-bottom: 2rem; }
.nac20-empty h3 { font-size: 1.2rem; font-weight: 600; color: #16344d; }
@media (max-width: 767px) { .nac20-hero { flex-direction: column; align-items: stretch; padding: 1.75rem; gap: 1.5rem; } .nac20-system-card { min-width: 0; } .nac20-section-heading { align-items: stretch; flex-direction: column; } .nac20-search { max-width: none; } .nac20-overview { margin-top: .75rem; } }
@media (prefers-reduced-motion: reduce) { .about-card { transition: none; } .about-card:hover, .about-card:focus { transform: none; } }
</style>
