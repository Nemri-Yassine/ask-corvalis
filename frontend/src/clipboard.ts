// Copy text to the clipboard. Some browsers / company setups block the modern
// API, so fall back to selecting the element's text and the older copy command.
export async function copyText(text: string, element?: HTMLElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    if (!element) return false
    const range = document.createRange()
    range.selectNodeContents(element)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    try {
      return document.execCommand('copy') // deprecated, but the only fallback left
    } catch {
      return false
    }
  }
}
