const CSRF_COOKIE_NAME = 'csrftoken'

export function getCsrfToken(): string {
  for (const cookieEntry of document.cookie.split(';')) {
    const entry = cookieEntry.trim()
    const separatorIndex = entry.indexOf('=')
    if (separatorIndex === -1 || entry.slice(0, separatorIndex) !== CSRF_COOKIE_NAME) {
      continue
    }

    try {
      return decodeURIComponent(entry.slice(separatorIndex + 1))
    } catch {
      return ''
    }
  }

  return ''
}
