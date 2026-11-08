import React from 'react'
import { renderToString } from 'react-dom/server'
import { describe, expect, it, beforeEach } from 'vitest'
import i18n from '../../src/i18n'
import { SafetyBlock } from '../../src/design/components/SafetyBlock'

describe('SafetyBlock commodity name rendering', () => {
  beforeEach(() => {
    i18n.changeLanguage('en')
  })

  it('renders mango correctly and does NOT contain potato', () => {
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      resolved: {
        commodity: {
          id: 'mango',
          name: 'mango',
          display_name: 'mango',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    expect(html).toContain('mango')
    expect(html.toLowerCase()).not.toContain('potato')
    expect(html).toContain('Cut <strong>mango</strong> kept in heat presents')
  })

  it('renders spinach correctly and does NOT contain potato', () => {
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      resolved: {
        commodity: {
          id: 'spinach',
          name: 'spinach',
          display_name: 'spinach',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    expect(html).toContain('spinach')
    expect(html.toLowerCase()).not.toContain('potato')
    expect(html).toContain('Cut <strong>spinach</strong> kept in heat presents')
  })

  it('renders onion correctly and does NOT contain potato', () => {
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      resolved: {
        commodity: {
          id: 'onion',
          name: 'onion',
          display_name: 'onion',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    expect(html).toContain('onion')
    expect(html.toLowerCase()).not.toContain('potato')
    expect(html).toContain('Cut <strong>onion</strong> kept in heat presents')
  })

  it('renders banana correctly and does NOT contain potato', () => {
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      resolved: {
        commodity: {
          id: 'banana',
          name: 'banana',
          display_name: 'banana',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    expect(html).toContain('banana')
    expect(html.toLowerCase()).not.toContain('potato')
    expect(html).toContain('Cut <strong>banana</strong> kept in heat presents')
  })

  it('uses local_name in preference to display_name when present', () => {
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      resolved: {
        commodity: {
          id: 'mango',
          name: 'mango',
          display_name: 'mango',
          local_name: 'aam',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    const visibleText = html.replace(/<[^>]*>/g, ' ')
    expect(visibleText).toContain('aam')
    expect(visibleText).not.toContain('mango')
    expect(visibleText.toLowerCase()).not.toContain('potato')
    expect(html).toContain('Cut <strong>aam</strong> kept in heat presents')
  })

  it('correctly substitutes {commodity_name} placeholder in custom advisory and action', () => {
    const result = {
      resolved: {
        commodity: {
          display_name: 'mango',
        },
      },
    }

    const html = renderToString(
      <SafetyBlock
        advisory="Cut {commodity_name} kept in heat presents microbial dangers."
        action="Do not seal {commodity_name} in plastic. Chill immediately."
        result={result}
      />
    )

    expect(html).toContain('Cut <strong>mango</strong> kept in heat presents microbial dangers.')
    expect(html).toContain('Do not seal <strong>mango</strong> in plastic. Chill immediately.')
    expect(html.toLowerCase()).not.toContain('potato')
  })

  it('replaces hardcoded potato if legacy advisory string is provided without template', () => {
    const result = {
      resolved: {
        commodity: {
          display_name: 'mango',
        },
      },
    }

    const html = renderToString(
      <SafetyBlock
        advisory="Cut potato stored at 30 °C ambient presents fatal Clostridium botulinum."
        action="Do not seal potato in plastic."
        result={result}
      />
    )

    expect(html).toContain('Cut <strong>mango</strong> stored at 30 °C ambient presents fatal Clostridium botulinum.')
    expect(html).toContain('Do not seal <strong>mango</strong> in plastic.')
    expect(html.toLowerCase()).not.toContain('potato')
  })

  it('switches to Marathi, runs the potato-cut-3days scenario, and confirms every string is in Marathi', () => {
    i18n.changeLanguage('mr')
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      commodityId: 'veg.potato.solanum_tuberosum',
      commodityName: 'Potato',
      resolved: {
        commodity: {
          id: 'veg.potato.solanum_tuberosum',
          name: 'Potato',
          display_name: 'potato',
        },
      },
      safety: {
        status: 'BLOCK',
        rule_id: 'FSSAI-SEC-16 / BOT-01',
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)

    // Marathi visible strings
    expect(html).toContain('असुरक्षित')
    expect(html).toContain('गंभीर सुरक्षा चेतावणी')
    expect(html).toContain('धोका संदर्भ: FSSAI-SEC-16 / BOT-01')
    expect(html).toContain('पॅकेजिंगने हे <strong>बटाटा</strong> वाचणार नाही')
    expect(html).toContain('उष्णतेत ठेवलेला कापलेला <strong>बटाटा</strong> घातक क्लॉस्ट्रिडियम बोट्युलिनम')
    expect(html).toContain('तातडीची कृती')
    expect(html).toContain('प्लास्टिकमध्ये सील करू नका. ताबडतोब ≤ 4 °C पर्यंत थंड करा')
    expect(html).toContain('त्याऐवजी काय करावे:')
    expect(html).toContain('1. ताबडतोब ≤ 4 °C पर्यंत थंड करा')
    expect(html).toContain('जिवाणूंची वाढ रोखण्यासाठी शीतगृहात किंवा चुरा केलेल्या बर्फावर ठेवा.')
    expect(html).toContain('2. 4–6 तासांच्या आत विका किंवा शिजवा')
    expect(html).toContain('इतक्या वेळापूर्वी कापलेला <strong>बटाटा</strong> आजच खाल्ला किंवा प्रक्रिया केला गेला पाहिजे.')
    expect(html).toContain('खोलीच्या तापमानाला कोणत्याही हवाबंद फिल्म किंवा पिशवीत सील करू नका.')
    expect(html).toContain('3. पुढच्या वेळी: प्रत्यक्ष विक्री होईपर्यंत कापू नका')
    expect(html).toContain('अखंड <strong>बटाटा</strong> दिवस ते आठवडे टिकतो. कापल्यामुळे त्याचे टिकण्याचे आयुष्य ताबडतोब नष्ट होते.')

    // Assert NO English strings are visible
    expect(html).not.toContain('UNSAFE')
    expect(html).not.toContain('CRITICAL SAFETY INTERLOCK')
    expect(html).not.toContain('HAZARD REF:')
    expect(html).not.toContain('PACKAGING WILL NOT SAVE')
    expect(html).not.toContain('ACTION REQUIRED')
    expect(html).not.toContain('WHAT TO DO INSTEAD')
    const visibleText = html.replace(/<[^>]*>/g, ' ')
    expect(visibleText.toLowerCase()).not.toContain('potato')
  })

  it('verifies the hazard reference code comes dynamically from result.safety.rule_id', () => {
    i18n.changeLanguage('en')
    const result = {
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      safety: {
        status: 'BLOCK',
        rule_id: 'SAFE-RULE-XYZ-99',
      },
      resolved: {
        commodity: {
          display_name: 'tomato',
        },
      },
    }

    const html = renderToString(<SafetyBlock result={result} />)
    expect(html).toContain('HAZARD REF: SAFE-RULE-XYZ-99')
  })
})
