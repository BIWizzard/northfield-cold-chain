// Names, wording, and the logo of the business this app is dressed as. To reskin it for another
// sample business, change this file and the colour primitives in tokens.css. Words for the data
// itself, such as shipments, loggers, and °C, stay in the views: they describe the data model.
const shortName = 'Northfield'
const productName = 'Exception Desk'

export default {
  companyName: 'Northfield Provisions',
  shortName,
  productName,
  // The product's full name, the heading on Home.
  fullProductName: 'Cold-Chain Exception Desk',
  // The repo's folder name, the root of Home's file tree.
  repoName: 'northfield-cold-chain',
  homeIntro:
    'Northfield Provisions ships fresh, frozen, and marinated product from its plants to its distribution ' +
    'centers, each load with a temperature logger. This desk shows the shipment records and logger readings ' +
    'as they sit in the repo, so you can look at the same files Claude Code reads.',
  footerNote: 'Synthetic training data. Northfield Provisions and its carriers are fictional.',
  // A 20 by 20 mark drawn in currentColor, so its colour comes from --color-brand-mark in tokens.css.
  logo: `
    <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
      <g stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none">
        <path d="M10 1.5v17M2.6 5.75l14.8 8.5M2.6 14.25l14.8-8.5" />
        <path d="M8 3.2l2 1.6 2-1.6M8 16.8l2-1.6 2 1.6" stroke-width="1.3" />
      </g>
    </svg>`,
  // The browser tab's title: the page names, most specific first, then the short name and product.
  // With no page it's just the short name and product, which the fallback <title> in index.html matches.
  title(pages = []) {
    return [...pages, shortName + ' ' + productName].join(' | ')
  },
}
