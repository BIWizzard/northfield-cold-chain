// Logger readings as an SVG line chart, with the category's limits as a shaded band and lines.
const WIDTH = 720
const HEIGHT = 260
const MARGIN = { top: 16, right: 96, bottom: 32, left: 44 }
const HOUR_MS = 60 * 60 * 1000

export default {
  name: 'LoggerChart',
  props: {
    readings: { type: Array, required: true },
    limits: Object,
    title: String,
  },
  data() {
    return { width: WIDTH, height: HEIGHT, margin: MARGIN }
  },
  computed: {
    viewBox() {
      return '0 0 ' + WIDTH + ' ' + HEIGHT
    },
    plotWidth() {
      return WIDTH - MARGIN.left - MARGIN.right
    },
    plotHeight() {
      return HEIGHT - MARGIN.top - MARGIN.bottom
    },
    times() {
      return this.readings.map((reading) => Date.parse(reading.timestamp))
    },
    temps() {
      return this.readings.map((reading) => reading.temp_c)
    },
    timeRange() {
      return { start: this.times[0], end: this.times[this.times.length - 1] }
    },
    // The temperature axis covers every reading and every limit, plus 1 °C of room.
    tempRange() {
      const values = [...this.temps]
      if (this.limits) {
        for (const value of [this.limits.min_c, this.limits.max_c]) {
          if (value !== null) values.push(value)
        }
      }
      return {
        low: Math.floor(Math.min(...values) - 1),
        high: Math.ceil(Math.max(...values) + 1),
      }
    },
    points() {
      return this.times.map((time, i) => this.x(time) + ',' + this.y(this.temps[i])).join(' ')
    },
    tempTicks() {
      const { low, high } = this.tempRange
      const step = [1, 2, 5, 10].find((size) => (high - low) / size <= 6) || 20
      const ticks = []
      for (let value = Math.ceil(low / step) * step; value <= high; value += step) {
        ticks.push({ value, y: this.y(value) })
      }
      return ticks
    },
    timeTicks() {
      const { start, end } = this.timeRange
      const hours = [1, 2, 3, 6, 12, 24].find((size) => (end - start) / (size * HOUR_MS) <= 8) || 48
      const step = hours * HOUR_MS
      const ticks = []
      for (let time = Math.ceil(start / step) * step; time <= end; time += step) {
        ticks.push({ time, x: this.x(time), label: new Date(time).toISOString().slice(11, 16) })
      }
      return ticks
    },
    band() {
      if (!this.limits) return null
      const top = this.y(this.limits.max_c ?? this.tempRange.high)
      const bottom = this.y(this.limits.min_c ?? this.tempRange.low)
      return { y: top, height: bottom - top }
    },
    limitLines() {
      if (!this.limits) return []
      return [
        { name: 'max', value: this.limits.max_c },
        { name: 'min', value: this.limits.min_c },
      ].map((line) => ({
        name: line.name,
        y: this.y(line.value),
        label: line.name + ' ' + line.value.toFixed(1) + ' °C',
      }))
    },
    caption() {
      const format = (time) => new Date(time).toISOString().slice(0, 16).replace('T', ' ')
      return (
        this.readings.length + ' readings, ' +
        format(this.timeRange.start) + ' to ' + format(this.timeRange.end) + ' UTC. Temperatures in °C.'
      )
    },
  },
  methods: {
    x(time) {
      const span = Math.max(this.timeRange.end - this.timeRange.start, 1)
      return MARGIN.left + ((time - this.timeRange.start) / span) * this.plotWidth
    },
    y(temp) {
      const { low, high } = this.tempRange
      return MARGIN.top + ((high - temp) / (high - low)) * this.plotHeight
    },
  },
  template: `
    <figure class="chart">
      <svg :viewBox="viewBox" role="img" :aria-label="title">
        <rect v-if="band" class="chart-band" :x="margin.left" :y="band.y" :width="plotWidth" :height="band.height" />

        <g v-for="tick in tempTicks" :key="'temp' + tick.value" class="chart-grid">
          <line :x1="margin.left" :x2="width - margin.right" :y1="tick.y" :y2="tick.y" />
          <text class="tick-label" text-anchor="end" :x="margin.left - 8" :y="tick.y" dy="0.32em">{{ tick.value }}</text>
        </g>

        <g v-for="tick in timeTicks" :key="'time' + tick.time" class="chart-grid">
          <line :x1="tick.x" :x2="tick.x" :y1="height - margin.bottom" :y2="height - margin.bottom + 4" />
          <text class="tick-label" text-anchor="middle" :x="tick.x" :y="height - margin.bottom + 18">{{ tick.label }}</text>
        </g>

        <g v-for="line in limitLines" :key="line.name" class="chart-limit">
          <line :x1="margin.left" :x2="width - margin.right" :y1="line.y" :y2="line.y" />
          <text :x="width - margin.right + 6" :y="line.y" dy="0.32em">{{ line.label }}</text>
        </g>

        <polyline class="chart-line" :points="points" />
      </svg>
      <figcaption>{{ caption }}</figcaption>
    </figure>
  `,
}
