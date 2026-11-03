// A repo path with a Copy button, so the path can be pasted into a prompt as @path.
export default {
  name: 'SourcePath',
  props: {
    label: { type: String, required: true },
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
    <div class="source-path">
      <span class="source-label">{{ label }}</span>
      <code>{{ path }}</code>
      <button type="button" @click="copy">{{ status === 'copied' ? 'Copied' : 'Copy' }}</button>
      <span v-if="status === 'failed'" class="copy-failed">Copy failed: select the path</span>
    </div>
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
