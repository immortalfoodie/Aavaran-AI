import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { queueFeedback } from '../../../offline/db'
import { syncPendingFeedbacks } from '../../../offline/sync'

interface FeedbackModalProps {
  isOpen: boolean
  resultId: string
  commodityId: string
  packageName: string
  shelfLifeDays: number
  district: string
  onClose: () => void
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  resultId,
  commodityId,
  packageName,
  shelfLifeDays,
  district,
  onClose,
}) => {
  const { t } = useTranslation()
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [submitted, setSubmitted] = useState<boolean>(false)
  const [notes, setNotes] = useState<string>('')

  if (!isOpen) return null

  const handleConfirm = async () => {
    setSubmitting(true)
    const followUpDate = new Date()
    followUpDate.setDate(followUpDate.getDate() + Math.max(1, shelfLifeDays))

    try {
      await queueFeedback({
        resultId,
        commodityId,
        actionTaken: `Packed using ${packageName}`,
        actualOutcomeDays: undefined,
        notes: notes || 'Farmer implemented recommendation in field',
        district,
        scheduledFollowUpDate: followUpDate.toISOString(),
      })

      // Attempt online sync
      syncPendingFeedbacks().catch(() => {})
      setSubmitted(true)
    } catch {
      setSubmitted(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-ink/75 z-50 flex items-center justify-center p-4"
    >
      <div className="bg-paper border-6 border-ink p-6 max-w-md w-full shadow-[10px_10px_0_var(--ink)] space-y-4">
        <div className="flex items-center justify-between border-b-3 border-ink pb-3">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤝</span>
            <h3 className="font-display uppercase text-lg sm:text-xl text-ink">
              {t('actions.i_did_this')}
            </h3>
          </div>
          <span className="font-mono text-xs font-bold bg-lime border-2 border-ink px-2 py-0.5">
            OUTCOME LOOP
          </span>
        </div>

        {submitted ? (
          <div className="space-y-4 py-2">
            <div className="border-3 border-ink bg-lime/30 p-4 flex items-center gap-3">
              <span className="text-3xl">✓</span>
              <div>
                <h4 className="font-display text-base text-ink uppercase">
                  {t('actions.schedule_saved')}
                </h4>
                <p className="font-body text-xs text-ink/80 mt-1">
                  We scheduled an automatic follow-up prompt to record how many days your produce stayed fresh.
                </p>
              </div>
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="min-h-[48px] px-6 font-display uppercase border-3 border-ink bg-ink text-paper cursor-pointer shadow-[4px_4px_0_var(--ink)]"
              >
                {t('actions.close')}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="font-body text-sm sm:text-base text-ink leading-relaxed">
              Did you use <strong>{packageName}</strong> for this batch? Logging your action helps calibrate shelf-life models for your local climate.
            </p>

            <div>
              <label className="font-display text-xs uppercase text-ink/80 block mb-1">
                Any notes? (Optional)
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. 5 bags packed this morning at mandi..."
                className="w-full border-3 border-ink p-2 font-body text-sm bg-paper text-ink focus:outline-none focus:bg-yellow/15"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="min-h-[48px] px-4 font-display uppercase border-3 border-ink bg-grey hover:bg-grey/80 cursor-pointer shadow-[4px_4px_0_var(--ink)]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleConfirm}
                className="min-h-[48px] px-6 font-display uppercase border-3 border-ink bg-yellow hover:bg-yellow/90 cursor-pointer shadow-[4px_4px_0_var(--ink)] flex items-center gap-2"
              >
                {submitting ? 'SAVING...' : 'CONFIRM & SCHEDULE'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default FeedbackModal
