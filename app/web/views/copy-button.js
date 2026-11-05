// A Copy button for a repo path, so the path can be pasted into a prompt as @path.
export default {
  name: 'CopyButton',
  props: {
    path: { type: String, required: true },
  },
  data() {
    return { status: '' }
  },
  methods: {
    async copy() {
      let copied
      try {
        await navigator.clipboard.writeText(this.path)
        copied = true
      } catch {
        copied = copyWithTextarea(this.path)
      }
      this.status = copied ? 'copied' : 'failed'
      setTimeout(() => {
        this.status = ''
      }, copied ? 1500 : 4000)
    },
  },
  template: `
    <button
      type="button"
      class="copy"
      :data-state="status || null"
      :aria-label="(status === 'copied' ? 'Copied ' : 'Copy ') + path"
      @click="copy"
    >{{ status === 'copied' ? 'Copied' : 'Copy' }}</button>
    <span v-if="status === 'failed'" class="copy-failed">Copy failed: select the path</span>
  `,
}

// Fallback for browsers where navigator.clipboard is unavailable or blocked.
// Returns whether the browser says the copy worked.
function copyWithTextarea(text) {
  const field = document.createElement('textarea')
  field.value = text
  field.setAttribute('readonly', '')
  field.style.position = 'fixed'
  field.style.opacity = '0'
  document.body.append(field)
  field.select()
  let copied = false
  try {
    copied = document.execCommand('copy')
  } catch {
    copied = false
  }
  field.remove()
  return copied
}
