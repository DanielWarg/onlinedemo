export function formatScoutDate(input) {
  if (!input) return ''
  const d = new Date(input)
  if (Number.isNaN(d.getTime())) return ''

  // Compact Swedish format without seconds.
  // Example: "ons 7 jan 07:00"
  const s = new Intl.DateTimeFormat('sv-SE', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  }).format(d)

  // sv-SE often includes trailing dots in abbreviations ("jan.", "ons.")
  return s.replace(/\./g, '')
}

