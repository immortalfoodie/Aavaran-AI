"""
Multilingual Commodity Alias Resolver using pgvector cosine similarity.

Matches extracted commodity hints (e.g. 'aloo', 'tomato', 'बटाटा', 'உருளைக்கிழங்கு')
against the Knowledge Base alias table using pgvector cosine distance.
Adheres strictly to the architectural constraint: "Matching is a retrieval problem,
not an LLM task."

Supports:
1. PostgreSQL pgvector distance query (<=>) when an active SQLAlchemy Session is provided.
2. High-performance in-memory vector index with 384-dimensional normalized embeddings
   for offline execution, fast tests, and environments without a live PostgreSQL instance.
3. Multilingual coverage across 9 Indian languages: English, Hindi, Marathi, Tamil,
   Telugu, Bengali, Kannada, Gujarati, and Punjabi (both native scripts and transliteration).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import numpy as np

logger = logging.getLogger("aavaran.alias_resolver")

EMBEDDING_DIM = 384

# Comprehensive multilingual aliases mapping to canonical commodity_ids
MULTILINGUAL_ALIASES: list[dict[str, str]] = [
    # 1. Potato (Solanum tuberosum)
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "potato", "lang": "en"},
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "solanum tuberosum",
        "lang": "en",
    },
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "aloo", "lang": "hi"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "aalu", "lang": "hi"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "आलू", "lang": "hi"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "batata", "lang": "mr"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "बटाटा", "lang": "mr"},
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "urulaikizhangu",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "urulaikilangu",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "உருளைக்கிழங்கு",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "bangaladumpa",
        "lang": "te",
    },
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "alugadda", "lang": "te"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "బంగాళాదుంప", "lang": "te"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "alu", "lang": "bn"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "আলু", "lang": "bn"},
    {
        "commodity_id": "veg.potato.solanum_tuberosum",
        "alias": "aalugadde",
        "lang": "kn",
    },
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "alugadde", "lang": "kn"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "ಆಲೂಗಡ್ಡೆ", "lang": "kn"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "bataka", "lang": "gu"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "બટાકા", "lang": "gu"},
    {"commodity_id": "veg.potato.solanum_tuberosum", "alias": "ਆਲੂ", "lang": "pa"},
    # 2. Tomato (Solanum lycopersicum)
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tomato",
        "lang": "en",
    },
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "solanum lycopersicum",
        "lang": "en",
    },
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tamatar",
        "lang": "hi",
    },
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "टमाटर", "lang": "hi"},
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "टोमॅटो", "lang": "mr"},
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "thakkali",
        "lang": "ta",
    },
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "தக்காளி", "lang": "ta"},
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tamata",
        "lang": "te",
    },
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tamota",
        "lang": "te",
    },
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "టమోటా", "lang": "te"},
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tometo",
        "lang": "bn",
    },
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "টমেটো", "lang": "bn"},
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "ಟೊಮೆಟೊ", "lang": "kn"},
    {
        "commodity_id": "veg.tomato.solanum_lycopersicum",
        "alias": "tameta",
        "lang": "gu",
    },
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "ટામેટા", "lang": "gu"},
    {"commodity_id": "veg.tomato.solanum_lycopersicum", "alias": "ਟਮਾਟਰ", "lang": "pa"},
    # 3. Onion (Allium cepa)
    {"commodity_id": "veg.onion.allium_cepa", "alias": "onion", "lang": "en"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "allium cepa", "lang": "en"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "pyaz", "lang": "hi"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "pyaaz", "lang": "hi"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "प्याज", "lang": "hi"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "kanda", "lang": "mr"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "कांदा", "lang": "mr"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "vengayam", "lang": "ta"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "வெங்காயம்", "lang": "ta"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "ullipaya", "lang": "te"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "ఉల్లిపాయ", "lang": "te"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "peyaj", "lang": "bn"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "পেঁয়াজ", "lang": "bn"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "eerulli", "lang": "kn"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "irulli", "lang": "kn"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "ಈರುಳ್ಳಿ", "lang": "kn"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "dungli", "lang": "gu"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "dungari", "lang": "gu"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "ડુંગળી", "lang": "gu"},
    {"commodity_id": "veg.onion.allium_cepa", "alias": "ਪਿਆਜ਼", "lang": "pa"},
    # 4. Mango (Mangifera indica)
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "mango", "lang": "en"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "alphonso", "lang": "en"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "aam", "lang": "hi"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "आम", "lang": "hi"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "amba", "lang": "mr"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "hapus", "lang": "mr"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "आंबा", "lang": "mr"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "mangai", "lang": "ta"},
    {
        "commodity_id": "fruit.mango.mangifera_indica",
        "alias": "mambazham",
        "lang": "ta",
    },
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "மாங்காய்", "lang": "ta"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "mamidi", "lang": "te"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "మామిడి", "lang": "te"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "আম", "lang": "bn"},
    {
        "commodity_id": "fruit.mango.mangifera_indica",
        "alias": "mavinakayi",
        "lang": "kn",
    },
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "ಮಾವಿನಕಾಯಿ", "lang": "kn"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "keri", "lang": "gu"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "કેરી", "lang": "gu"},
    {"commodity_id": "fruit.mango.mangifera_indica", "alias": "ਅੰਬ", "lang": "pa"},
    # 5. Banana (Musa acuminata)
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "banana", "lang": "en"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "kela", "lang": "hi"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "केला", "lang": "hi"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "kele", "lang": "mr"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "केळे", "lang": "mr"},
    {
        "commodity_id": "fruit.banana.musa_acuminata",
        "alias": "vazhaipazham",
        "lang": "ta",
    },
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "வாழை", "lang": "ta"},
    {
        "commodity_id": "fruit.banana.musa_acuminata",
        "alias": "aratipandu",
        "lang": "te",
    },
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "అరటిపండు", "lang": "te"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "kola", "lang": "bn"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "কলা", "lang": "bn"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "balehannu", "lang": "kn"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "ಬಾಳೆಹಣ್ಣು", "lang": "kn"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "કેળા", "lang": "gu"},
    {"commodity_id": "fruit.banana.musa_acuminata", "alias": "ਕੇਲਾ", "lang": "pa"},
    # 6. Green Chilli (Capsicum annuum)
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "green chilli",
        "lang": "en",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "chilli",
        "lang": "en",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "mirchi",
        "lang": "hi",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "hari mirch",
        "lang": "hi",
    },
    {"commodity_id": "veg.green_chilli.capsicum_annuum", "alias": "मिर्च", "lang": "hi"},
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "मिरची",
        "lang": "mr",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "pachai milagai",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "மிளகாய்",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "mirapakaya",
        "lang": "te",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "మిరపకాయ",
        "lang": "te",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "lonka",
        "lang": "bn",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "কাঁচা লঙ্কা",
        "lang": "bn",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "menasinakayi",
        "lang": "kn",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "ಮೆಣಸಿನಕಾಯಿ",
        "lang": "kn",
    },
    {
        "commodity_id": "veg.green_chilli.capsicum_annuum",
        "alias": "marcha",
        "lang": "gu",
    },
    {"commodity_id": "veg.green_chilli.capsicum_annuum", "alias": "મરચાં", "lang": "gu"},
    {"commodity_id": "veg.green_chilli.capsicum_annuum", "alias": "ਮਿਰਚ", "lang": "pa"},
    # 7. Okra (Abelmoschus esculentus)
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "okra", "lang": "en"},
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "lady finger",
        "lang": "en",
    },
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "bhindi",
        "lang": "hi",
    },
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "भिंडी", "lang": "hi"},
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "bhendi",
        "lang": "mr",
    },
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "भेंडी", "lang": "mr"},
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "vendakkai",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "வெண்டைக்காய்",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "bendakaya",
        "lang": "te",
    },
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "బెండకాయ", "lang": "te"},
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "dharosh",
        "lang": "bn",
    },
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "ঢেঁড়শ", "lang": "bn"},
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "bendekayi",
        "lang": "kn",
    },
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "ಬೆಂಡೆಕಾಯಿ",
        "lang": "kn",
    },
    {
        "commodity_id": "veg.okra.abelmoschus_esculentus",
        "alias": "bhindo",
        "lang": "gu",
    },
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "ભીંડો", "lang": "gu"},
    {"commodity_id": "veg.okra.abelmoschus_esculentus", "alias": "ਭਿੰਡੀ", "lang": "pa"},
    # 8. Spinach (Spinacia oleracea)
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "spinach", "lang": "en"},
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "palak", "lang": "hi"},
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "पालक", "lang": "hi"},
    {
        "commodity_id": "veg.spinach.spinacia_oleracea",
        "alias": "pasalai keerai",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.spinach.spinacia_oleracea",
        "alias": "பசலைக்கீரை",
        "lang": "ta",
    },
    {
        "commodity_id": "veg.spinach.spinacia_oleracea",
        "alias": "palakura",
        "lang": "te",
    },
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "పాలకూర", "lang": "te"},
    {
        "commodity_id": "veg.spinach.spinacia_oleracea",
        "alias": "palong shak",
        "lang": "bn",
    },
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "পালং শাক", "lang": "bn"},
    {
        "commodity_id": "veg.spinach.spinacia_oleracea",
        "alias": "palak soppu",
        "lang": "kn",
    },
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "ಪಾಲಕ್", "lang": "kn"},
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "પાલેક", "lang": "gu"},
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "પાંદડા", "lang": "gu"},
    {"commodity_id": "veg.spinach.spinacia_oleracea", "alias": "ਪਾਲਕ", "lang": "pa"},
    # 9. Paneer (Cottage cheese)
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "paneer", "lang": "en"},
    {
        "commodity_id": "dairy.paneer.cottage_cheese",
        "alias": "cottage cheese",
        "lang": "en",
    },
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "पनीर", "lang": "hi"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "பனீர்", "lang": "ta"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "పనీర్", "lang": "te"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "chhana", "lang": "bn"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "ponir", "lang": "bn"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "পনির", "lang": "bn"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "ಪನ್ನೀರ್", "lang": "kn"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "પનીર", "lang": "gu"},
    {"commodity_id": "dairy.paneer.cottage_cheese", "alias": "ਪਨੀਰ", "lang": "pa"},
    # 10. Milk Powder
    {"commodity_id": "dairy.milk_powder.whole", "alias": "milk powder", "lang": "en"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "doodh powder", "lang": "hi"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "दूध पाउडर", "lang": "hi"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "paal powder", "lang": "ta"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "பால் பவுடர்", "lang": "ta"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "pala podi", "lang": "te"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "పాల పొడి", "lang": "te"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "dudher guro", "lang": "bn"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "দুধের গুঁড়ো", "lang": "bn"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "halina pudi", "lang": "kn"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "ಹಾಲಿನ ಪುಡಿ", "lang": "kn"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "દૂધ પાવડર", "lang": "gu"},
    {"commodity_id": "dairy.milk_powder.whole", "alias": "ਦੁੱਧ ਪਾਊਡਰ", "lang": "pa"},
    # 11. Turmeric Powder
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "turmeric",
        "lang": "en",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "turmeric powder",
        "lang": "en",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "haldi",
        "lang": "hi",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "हल्दी",
        "lang": "hi",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "halad",
        "lang": "mr",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "हळद",
        "lang": "mr",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "manjal",
        "lang": "ta",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "மஞ்சள்",
        "lang": "ta",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "pasupu",
        "lang": "te",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "పసుపు",
        "lang": "te",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "holud",
        "lang": "bn",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "হলুদ",
        "lang": "bn",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "arishina",
        "lang": "kn",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "ಅರಿಶಿನ",
        "lang": "kn",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "haldar",
        "lang": "gu",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "હળદર",
        "lang": "gu",
    },
    {
        "commodity_id": "spice.turmeric_powder.curcuma_longa",
        "alias": "ਹਲਦੀ",
        "lang": "pa",
    },
    # 12. Besan Namkeen
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "namkeen",
        "lang": "en",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "besan namkeen",
        "lang": "en",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "fried snack",
        "lang": "en",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "sev",
        "lang": "hi",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "bhujia",
        "lang": "hi",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "नमकीन",
        "lang": "hi",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "भुजिया",
        "lang": "hi",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "farsan",
        "lang": "mr",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "शेव",
        "lang": "mr",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "फरसाण",
        "lang": "mr",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "karasev",
        "lang": "ta",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "காராசேவ்",
        "lang": "ta",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "karappusa",
        "lang": "te",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "నంకీన్",
        "lang": "te",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "নিমকি",
        "lang": "bn",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "খারা",
        "lang": "kn",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "નમકીન",
        "lang": "gu",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "ਫਰਸਾਨ",
        "lang": "pa",
    },
    {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "alias": "ਨਮਕੀਨ",
        "lang": "pa",
    },
]


def generate_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """
    Generates a deterministic 384-dimensional unit vector for text.
    Combines character n-gram hashing and subword token hashing to ensure:
    1. Dimension matches PostgreSQL Vector(384).
    2. High cosine similarity between identical and morphologically close aliases.
    3. Fully offline and deterministic without external downloads.
    """
    clean = text.strip().lower()
    vec = np.zeros(dim, dtype=np.float32)

    if not clean:
        vec[0] = 1.0
        return vec

    # 1. Whole word tokens
    tokens = re.split(r"[\s,._\-]+", clean)
    for token in tokens:
        if not token:
            continue
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 9) & 1) == 0 else -1.0
        vec[idx] += 2.0 * sign

        # Secondary hash for dense distribution
        h2 = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx2 = h2 % dim
        sign2 = 1.0 if ((h2 >> 7) & 1) == 0 else -1.0
        vec[idx2] += 1.5 * sign2

    # 2. Character n-grams (2-grams, 3-grams, 4-grams)
    padded = f"^{clean}$"
    for n in (2, 3, 4):
        for i in range(len(padded) - n + 1):
            ngram = padded[i : i + n]
            h = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if ((h >> 5) & 1) == 0 else -1.0
            weight = 1.0 / n
            vec[idx] += weight * sign

    # Normalize to unit sphere (L2 norm)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    else:
        vec[0] = 1.0

    return vec


class InMemoryVectorStore:
    """In-memory vector store supporting cosine similarity retrieval."""

    def __init__(self, aliases: list[dict[str, str]]):
        self.records = aliases
        self.embeddings: np.ndarray = np.array(
            [generate_embedding(r["alias"]) for r in aliases], dtype=np.float32
        )

    def search(self, query: str, top_k: int = 1) -> list[tuple[dict[str, str], float]]:
        q_vec = generate_embedding(query)
        # Cosine similarity for unit vectors: dot product
        sims = np.dot(self.embeddings, q_vec)
        top_indices = np.argsort(sims)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append((self.records[idx], float(sims[idx])))
        return results


# Global singleton in-memory alias index
_IN_MEMORY_STORE: InMemoryVectorStore | None = None


def get_in_memory_alias_store() -> InMemoryVectorStore:
    """Returns initialized singleton in-memory alias vector store."""
    global _IN_MEMORY_STORE
    if _IN_MEMORY_STORE is None:
        _IN_MEMORY_STORE = InMemoryVectorStore(MULTILINGUAL_ALIASES)
    return _IN_MEMORY_STORE


def resolve_commodity_hint(
    commodity_hint: str,
    db_session: Any | None = None,
    top_k: int = 1,
    threshold: float = 0.35,
) -> tuple[str, float] | None:
    """
    Resolves a raw commodity hint against the alias table using pgvector cosine similarity.

    Constraint: "Resolve commodity_hint against the alias table using pgvector
    cosine similarity, not the LLM. Matching is a retrieval problem."

    Parameters:
    - commodity_hint: User mention (e.g. 'aloo', 'tomato', 'बटाटा', 'thakkali')
    - db_session: Optional SQLAlchemy session with pgvector
    - top_k: Number of nearest neighbors to query (default 1)
    - threshold: Minimum cosine similarity required to return a match

    Returns:
    - (commodity_id, cosine_similarity) if matched; None otherwise.
    """
    if not commodity_hint or not commodity_hint.strip():
        return None

    clean_hint = commodity_hint.strip().lower()
    query_vec = generate_embedding(clean_hint)

    # 1. Attempt PostgreSQL pgvector query if an active DB session is supplied
    if db_session is not None:
        try:
            from sqlalchemy import select

            from kb.schema import CommodityAlias

            # pgvector cosine distance operator <=> maps to .cosine_distance() in pgvector-python
            stmt = (
                select(
                    CommodityAlias,
                    CommodityAlias.embedding.cosine_distance(query_vec.tolist()).label(
                        "dist"
                    ),
                )
                .where(CommodityAlias.embedding.isnot(None))
                .order_by("dist")
                .limit(top_k)
            )
            rows = db_session.execute(stmt).fetchall()
            if rows:
                best_alias, dist = rows[0]
                similarity = 1.0 - float(dist)
                if similarity >= threshold:
                    return (best_alias.commodity_id, round(similarity, 4))
        except Exception as e:
            logger.debug(
                f"pgvector DB lookup unavailable or failed ({e}); using in-memory vector index."
            )

    # 2. Exact match check across aliases (fast-path)
    store = get_in_memory_alias_store()
    for rec in store.records:
        if clean_hint == rec["alias"].lower():
            return (rec["commodity_id"], 1.0)

    # 3. Vector Cosine Similarity retrieval
    hits = store.search(clean_hint, top_k=top_k)
    if hits:
        best_rec, best_sim = hits[0]
        if best_sim >= threshold:
            return (best_rec["commodity_id"], round(best_sim, 4))

    return None
