const CSRF_COOKIE_NAME = 'csrftoken'
const CSRF_META_SELECTOR = 'meta[name="csrf-token"]'

export function getCsrfToken(): string {
  const injectedToken = document.querySelector<HTMLMetaElement>(CSRF_META_SELECTOR)?.content
  if (injectedToken) {
    return injectedToken
  }

  let csrfToken = ''
  for (const cookieEntry of document.cookie.split(';')) {
    const entry = cookieEntry.trim()
    const separatorIndex = entry.indexOf('=')
    if (separatorIndex === -1 || entry.slice(0, separatorIndex) !== CSRF_COOKIE_NAME) {
      continue
    }

    try {
      csrfToken = decodeURIComponent(entry.slice(separatorIndex + 1))
    } catch {
      csrfToken = ''
    }
  }

  return csrfToken
}
