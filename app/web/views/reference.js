import SourcePath from './source-path.js'

// The carriers, lanes, and product categories that shipment rows refer to, as they are in the files.
// Records only: nothing here groups or counts shipments.
export default {
  name: 'ReferenceView',
  components: { SourcePath },
  props: {
    reference: Object,
    loading: Boolean,
    error: String,
  },
  computed: {
    categories() {
      return Object.entries(this.reference.categories).map(([name, limits]) => ({ name, limits }))
    },
    // One shared °C scale for every category's range, with room on both sides and 0 always on it.
    scale() {
      const nums = [0, ...this.categories.flatMap(({ limits }) => (
        [limits.min_c, limits.max_c].filter((n) => typeof n === 'number')
      ))]
      return {
        low: Math.floor((Math.min(...nums) - 5) / 5) * 5,
        high: Math.ceil((Math.max(...nums) + 3) / 5) * 5,
      }
    },
  },
  methods: {
    limit(value) {
      return typeof value === 'number' ? value.toFixed(1) : null
    },
    scaleX(value) {
      const { low, high } = this.scale
      return 4 + ((value - low) / (high - low)) * 252
    },
    range(limits) {
      const left = this.scaleX(typeof limits.min_c === 'number' ? limits.min_c : this.scale.low)
      const right = this.scaleX(typeof limits.max_c === 'number' ? limits.max_c : this.scale.high)
      return { x: left, width: Math.max(right - left, 2) }
    },
    rangeLabel(limits) {
      const low = this.limit(limits.min_c) ?? 'no lower limit'
      const high = this.limit(limits.max_c) ?? 'no upper limit'
      return 'Allowed range ' + low + ' to ' + high + ' °C, on a scale from ' + this.scale.low + ' to ' + this.scale.high + ' °C'
    },
  },
  template: `
    <div class="page-head">
      <div>
        <h1>Reference</h1>
        <p class="sub">The carriers, lanes, and temperature limits that shipment rows refer to.</p>
      </div>
    </div>

    <div v-if="error" class="panel"><p class="message">{{ error }}</p></div>
    <p v-else-if="loading || !reference" class="muted">Loading…</p>
    <div v-else class="ref-grid">
      <div class="stack">
        <section class="panel" aria-labelledby="carriers-title">
          <div class="panel-head"><h2 id="carriers-title">Carriers<span class="count">{{ reference.carriers.length }}</span></h2></div>
          <div class="sources"><source-path label="Reads" :path="reference.carriers_source" /></div>
          <div class="table-wrap">
            <table class="compact">
              <thead><tr><th scope="col">carrier_id</th><th scope="col">name</th></tr></thead>
              <tbody>
                <tr v-for="carrier in reference.carriers" :key="carrier.carrier_id">
                  <td class="mono">{{ carrier.carrier_id }}</td>
                  <td>{{ carrier.name }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel" aria-labelledby="categories-title">
          <div class="panel-head"><h2 id="categories-title">Product categories<span class="count">{{ categories.length }}</span></h2></div>
          <div class="sources"><source-path label="Reads" :path="reference.thresholds_source" /></div>
          <ul class="categories">
            <li v-for="category in categories" :key="category.name">
              <span class="category">{{ category.name }}</span>
              <svg class="scale" viewBox="0 0 260 22" role="img" :aria-label="rangeLabel(category.limits)">
                <rect class="track" x="4" y="3" width="252" height="8" rx="1" />
                <rect class="range" :x="range(category.limits).x" y="3" :width="range(category.limits).width" height="8" rx="1" />
                <line class="zero" :x1="scaleX(0)" :x2="scaleX(0)" y1="0" y2="14" />
                <text x="4" y="21">{{ scale.low }}</text>
                <text :x="scaleX(0)" y="21" text-anchor="middle">0</text>
                <text x="256" y="21" text-anchor="end">+{{ scale.high }} °C</text>
              </svg>
              <span class="limits">
                <span><span class="key">min_c</span><span v-if="limit(category.limits.min_c) === null" class="none">none</span><template v-else>{{ limit(category.limits.min_c) }}</template></span>
                <span><span class="key">max_c</span><span v-if="limit(category.limits.max_c) === null" class="none">none</span><template v-else>{{ limit(category.limits.max_c) }}</template></span>
                <span><span class="key">max_minutes_out_of_range</span>{{ category.limits.max_minutes_out_of_range }}</span>
              </span>
            </li>
          </ul>
        </section>
      </div>

      <section class="panel" aria-labelledby="lanes-title">
        <div class="panel-head"><h2 id="lanes-title">Lanes<span class="count">{{ reference.lanes.length }}</span></h2></div>
        <div class="sources"><source-path label="Reads" :path="reference.lanes_source" /></div>
        <div class="table-wrap">
          <table class="compact">
            <thead>
              <tr>
                <th scope="col">lane_id</th><th scope="col">origin</th><th scope="col">destination</th>
                <th scope="col" class="num">transit_hours</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="lane in reference.lanes" :key="lane.lane_id">
                <td class="mono">{{ lane.lane_id }}</td>
                <td>{{ lane.origin }}</td>
                <td>{{ lane.destination }}</td>
                <td class="num mono">{{ lane.transit_hours }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  `,
}
