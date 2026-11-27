/** Human label for a policy rule params key: `window_days` → "Window days". */
export function paramLabel(key: string) {
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}
