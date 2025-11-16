const AUTH_FLAG_KEY = 'random-quiz-authenticated'

const hasStorage = () => typeof window !== 'undefined' && window.localStorage

const safeSet = (value) => {
  if (!hasStorage()) return
  try {
    window.localStorage.setItem(AUTH_FLAG_KEY, value)
  } catch {}
}

const safeGet = () => {
  if (!hasStorage()) return null
  try {
    return window.localStorage.getItem(AUTH_FLAG_KEY)
  } catch {
    return null
  }
}

const safeRemove = () => {
  if (!hasStorage()) return
  try {
    window.localStorage.removeItem(AUTH_FLAG_KEY)
  } catch {}
}

export const markAuthenticated = () => safeSet('1')
export const clearAuthFlag = () => safeRemove()
export const hasAuthFlag = () => safeGet() === '1'
