import CopyButton from './copy-button.js'

// A repo path with a Copy button, so the path can be pasted into a prompt as @path.
export default {
  name: 'SourcePath',
  components: { CopyButton },
  props: {
    label: { type: String, required: true },
    path: { type: String, required: true },
  },
  template: `
    <div class="source-path">
      <span class="source-label">{{ label }}</span>
      <code>{{ path }}</code>
      <copy-button :path="path" />
    </div>
  `,
}
