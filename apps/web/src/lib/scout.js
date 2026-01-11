export function formatScoutSource(rawSource) {
  if (!rawSource) return ''
  // Data ibland har suffix som "(redigerad)" vilket gör listor visuellt skeva.
  // Vi normaliserar endast för display (ingen datamodell ändras).
  return String(rawSource)
    .replace(/\s*(\(\s*redigerad\s*\)|[-–—]?\s*redigerad)\s*$/i, '')
    .trim()
}

