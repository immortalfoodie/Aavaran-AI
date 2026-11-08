export const COMMODITY_IMAGES: Record<string, string> = {
  // Keys must match the commodity_id from your KB exactly
  "veg.potato.solanum_tuberosum": "/images/crops/potato.jpg",
  "veg.tomato.solanum_lycopersicum": "/images/crops/tomato.jpg",
  "veg.onion.allium_cepa": "/images/crops/onion.jpg",
  "fruit.banana.musa": "/images/crops/banana.jpg",
  "fruit.banana.musa_acuminata": "/images/crops/banana.jpg",
  "fruit.mango.mangifera_indica": "/images/crops/mango.jpg",
  "veg.okra.abelmoschus_esculentus": "/images/crops/okra.jpg",
  "veg.spinach.spinacia_oleracea": "/images/crops/spinach.jpg",
  "veg.green_chilli.capsicum_annuum": "/images/crops/green_chilli.jpg",
  // Processed / dry / dairy foods
  "proc.namkeen.besan": "/images/crops/namkeen.jpg",
  "processed.besan_namkeen.fried_snack": "/images/crops/namkeen.jpg",
  "food.snack.namkeen_bhujia": "/images/crops/namkeen.jpg",
  "spice.turmeric.curcuma_longa": "/images/crops/turmeric.jpg",
  "spice.turmeric_powder.curcuma_longa": "/images/crops/turmeric.jpg",
  "dairy.paneer.fresh": "/images/crops/paneer.jpg",
  "dairy.paneer.cottage_cheese": "/images/crops/paneer.jpg",
  "proc.milk_powder.skimmed": "/images/crops/milk_powder.jpg",
  "dairy.milk_powder.whole": "/images/crops/milk_powder.jpg",
}

// Fallback: a neutral market/produce image for unmapped commodities
export const FALLBACK_CROP_IMAGE = "/images/crops/market_produce.jpg"

export function getCommodityImage(commodityId?: string | null): string {
  if (!commodityId) return FALLBACK_CROP_IMAGE

  // 1. Try exact match first
  if (COMMODITY_IMAGES[commodityId]) return COMMODITY_IMAGES[commodityId]

  const lower = commodityId.toLowerCase()

  // 2. Try prefix match (e.g. "veg.tomato.cherry" -> "veg.tomato.*")
  const prefix = commodityId.split('.').slice(0, 2).join('.')
  if (prefix) {
    const prefixMatch = Object.entries(COMMODITY_IMAGES).find(([key]) =>
      key.startsWith(prefix)
    )
    if (prefixMatch) return prefixMatch[1]
  }

  // 3. Keyword heuristic search for standard crops
  const cropKeywords: Record<string, string> = {
    potato: '/images/crops/potato.jpg',
    tomato: '/images/crops/tomato.jpg',
    onion: '/images/crops/onion.jpg',
    banana: '/images/crops/banana.jpg',
    mango: '/images/crops/mango.jpg',
    okra: '/images/crops/okra.jpg',
    spinach: '/images/crops/spinach.jpg',
    chilli: '/images/crops/green_chilli.jpg',
    namkeen: '/images/crops/namkeen.jpg',
    paneer: '/images/crops/paneer.jpg',
    turmeric: '/images/crops/turmeric.jpg',
  }

  for (const [kw, path] of Object.entries(cropKeywords)) {
    if (lower.includes(kw)) {
      return path
    }
  }

  return FALLBACK_CROP_IMAGE
}
