// Date labels shared by the views. Dates in the data are UTC, written as YYYY-MM-DD.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "2026-10-26" as "Oct 26".
export function shortDate(date) {
  const [, month, day] = date.split('-').map(Number)
  return MONTHS[month - 1] + ' ' + day
}
