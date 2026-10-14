import vietnamese from './vi.json'
import Vue from 'vue'
import VueI18n from 'vue-i18n'
import Formatter from './formatter'
import { pfLocales } from '@/globals/pfLocales'

Vue.use(VueI18n)

const locale = 'vi' // default locale
export const formatter = new Formatter({ locale })

const i18n = new VueI18n({
  locale,
  formatter,
  messages: { vi: vietnamese, 'en-US': {} },
  silentTranslationWarn: true, // suppress console warn on missing translations
  missing: (locale, key, vm, values) => {
    key = key.replace(/packetfence/gi, 'NAC20')
    // uncomment the next line to debug missing translations
    // console.error(`[Translation] missing: locale=${locale}, key=${key}, values=${JSON.stringify(values)}`)
    if (!values || !values[0] || !key.includes('{') || !key.includes('}')) return key
    // handle formatting manually
    try {
      return formatter.interpolate(key, values[0])[0]
    } catch (err) {
      // eslint-disable-next-line
      console.error(err)
    }
    return key
  }
})

export default i18n

// available languages
// first item is default
// labels are in English
// static definition is less resource-intensive than consuming /api/v1/translations
export const languages = pfLocales
  .filter(({ is_ui }) => is_ui)
  .map(({ label, locale }) => {
    return {
      language: locale.split('_')[0],
      locale,
      label
    }
  })
