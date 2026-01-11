/**
 * Shared urgency helper for project due dates
 * Single source of truth for deadline urgency logic
 */

export function getDueUrgency(dueDate) {
  if (!dueDate) {
    return {
      daysLeft: null,
      variant: 'muted',
      label: null,
      normalizedDate: null
    }
  }

  // Normalize due_date string to YYYY-MM-DD (single source of truth)
  let normalizedDate = null
  
  if (typeof dueDate === 'string') {
    // If contains T: take s.split('T')[0]
    if (dueDate.includes('T')) {
      normalizedDate = dueDate.split('T')[0]
    }
    // Else if contains space: take s.split(' ')[0]
    else if (dueDate.includes(' ')) {
      normalizedDate = dueDate.split(' ')[0]
    }
    // Else if already matches /^\d{4}-\d{2}-\d{2}$/: keep as-is
    else if (/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) {
      normalizedDate = dueDate
    }
    // Else: invalid format
    else {
      return {
        daysLeft: null,
        variant: 'muted',
        label: null,
        normalizedDate: null
      }
    }
  } else {
    // Not a string, invalid
    return {
      daysLeft: null,
      variant: 'muted',
      label: null,
      normalizedDate: null
    }
  }

  // Parse YYYY-MM-DD deterministically: split('-') → new Date(y, m-1, d)
  const [year, month, day] = normalizedDate.split('-').map(Number)
  
  // Validate parsed values
  if (isNaN(year) || isNaN(month) || isNaN(day)) {
    return {
      daysLeft: null,
      variant: 'muted',
      label: null,
      normalizedDate: null
    }
  }
  
  const due = new Date(year, month - 1, day)
  
  // Compute today as local midnight
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  
  // Calculate days left (floor division)
  const diffMs = due.getTime() - today.getTime()
  const daysLeft = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  // Apply rules
  if (daysLeft === 3) {
    return {
      daysLeft: 3,
      variant: 'warning',
      label: '3 dagar kvar',
      normalizedDate
    }
  }

  if (daysLeft === 2) {
    return {
      daysLeft: 2,
      variant: 'danger',
      label: '2 dagar kvar',
      normalizedDate
    }
  }

  if (daysLeft === 1) {
    return {
      daysLeft: 1,
      variant: 'danger',
      label: '1 dag kvar',
      normalizedDate
    }
  }

  if (daysLeft <= 0) {
    return {
      daysLeft: daysLeft,
      variant: 'danger',
      label: 'Försenad',
      normalizedDate
    }
  }

  // Default: muted, no label
  return {
    daysLeft: daysLeft,
    variant: 'muted',
    label: null,
    normalizedDate
  }
}

