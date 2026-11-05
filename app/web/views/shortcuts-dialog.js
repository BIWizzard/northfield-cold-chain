// The keyboard shortcuts list, opened with ? or the Shortcuts button. Esc or Close shuts it.
export default {
  name: 'ShortcutsDialog',
  props: {
    open: Boolean,
    shortcuts: { type: Array, required: true },
  },
  emits: ['close'],
  watch: {
    open(open) {
      const dialog = this.$refs.dialog
      if (open && !dialog.open) dialog.showModal()
      if (!open && dialog.open) dialog.close()
    },
  },
  methods: {
    // A click on the dialog element itself, rather than its contents, is a click on the backdrop.
    closeFromBackdrop(event) {
      if (event.target === this.$refs.dialog) this.$refs.dialog.close()
    },
  },
  template: `
    <dialog ref="dialog" class="shortcuts" aria-labelledby="shortcuts-title" @close="$emit('close')" @click="closeFromBackdrop">
      <div class="panel-head">
        <h2 id="shortcuts-title">Keyboard shortcuts</h2>
        <button class="text-button" type="button" @click="$refs.dialog.close()">Close</button>
      </div>
      <dl class="keys">
        <template v-for="shortcut in shortcuts" :key="shortcut.action">
          <dt><template v-for="(key, index) in shortcut.keys" :key="key">{{ index ? ' ' : '' }}<kbd>{{ key }}</kbd></template></dt>
          <dd>{{ shortcut.action }}</dd>
        </template>
      </dl>
    </dialog>
  `,
}
