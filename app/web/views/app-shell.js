// The frame around every page: top bar with the breadcrumb, the left rail of sections, and the
// status bar. The page itself goes in the default slot. The rail is built from the `nav` prop,
// so adding a section in app.js adds its rail entry here with no change to this file.

// Drawn when a section doesn't give its own icon.
const DEFAULT_ICON = 'M3.5 3.5h11v11h-11z'

export default {
  name: 'AppShell',
  props: {
    nav: { type: Array, required: true },
    crumbs: { type: Array, required: true },
    host: String,
  },
  emits: ['show-shortcuts'],
  data() {
    return { defaultIcon: DEFAULT_ICON }
  },
  methods: {
    focusMain() {
      this.$refs.main.focus()
    },
  },
  template: `
    <a class="skip-link" href="#main" @click.prevent="focusMain">Skip to content</a>
    <div class="shell">
      <header class="topbar chrome">
        <a class="wordmark" href="#/" aria-label="Northfield Exception Desk, home">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <g stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none">
              <path d="M10 1.5v17M2.6 5.75l14.8 8.5M2.6 14.25l14.8-8.5" />
              <path d="M8 3.2l2 1.6 2-1.6M8 16.8l2-1.6 2 1.6" stroke-width="1.3" />
            </g>
          </svg>
          <strong>Northfield</strong><span>Exception Desk</span>
        </a>
        <nav class="crumbs" aria-label="Location">
          <template v-for="(crumb, index) in crumbs" :key="index">
            <span v-if="index" class="sep" aria-hidden="true">/</span>
            <a v-if="crumb.href && index < crumbs.length - 1" :href="crumb.href">{{ crumb.label }}</a>
            <span v-else :aria-current="index === crumbs.length - 1 ? 'page' : null">{{ crumb.label }}</span>
          </template>
        </nav>
        <div class="top-actions">
          <span class="host" title="Where the app is served">{{ host }}</span>
          <button class="btn-chrome" type="button" @click="$emit('show-shortcuts')">Shortcuts <kbd>?</kbd></button>
        </div>
      </header>

      <nav class="rail chrome" aria-label="Sections">
        <ul>
          <li v-for="item in nav" :key="item.label">
            <a :href="item.href" :aria-current="item.current ? 'page' : null">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"
                   stroke-linejoin="round" aria-hidden="true"><path :d="item.icon || defaultIcon" /></svg>
              <span>{{ item.label }}</span>
              <span v-if="item.key" class="hint" aria-hidden="true">g {{ item.key }}</span>
            </a>
          </li>
        </ul>
        <p class="rail-note">Synthetic training data. Northfield Provisions and its carriers are fictional.</p>
      </nav>

      <main ref="main" id="main" class="main" tabindex="-1">
        <div class="page"><slot /></div>
      </main>

      <footer class="statusbar chrome">
        <span><i class="dot" aria-hidden="true"></i>Serving from this laptop</span>
        <span>Files under <code>data/</code> are read on every request</span>
        <span class="push">Press <kbd>?</kbd> for keyboard shortcuts</span>
      </footer>
    </div>
  `,
}
