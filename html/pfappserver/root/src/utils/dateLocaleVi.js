// date-fns v1 locale for relative times. Numeric date formats use DD/MM/YYYY.
const phrases = {
  lessThanXSeconds: 'dưới {{count}} giây',
  xSeconds: '{{count}} giây',
  halfAMinute: 'nửa phút',
  lessThanXMinutes: 'dưới {{count}} phút',
  xMinutes: '{{count}} phút',
  aboutXHours: 'khoảng {{count}} giờ',
  xHours: '{{count}} giờ',
  xDays: '{{count}} ngày',
  aboutXMonths: 'khoảng {{count}} tháng',
  xMonths: '{{count}} tháng',
  aboutXYears: 'khoảng {{count}} năm',
  xYears: '{{count}} năm',
  overXYears: 'hơn {{count}} năm',
  almostXYears: 'gần {{count}} năm'
}

export default {
  distanceInWords: {
    localize (token, count, options = {}) {
      const result = (phrases[token] || '{{count}}').replace('{{count}}', count)
      if (!options.addSuffix) return result
      return options.comparison > 0 ? `sau ${result}` : `${result} trước`
    }
  }
}
