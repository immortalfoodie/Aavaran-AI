/**
 * Background synchronization module for Aavaran offline queue.
 * Automatically flushes pending feedback entries to /api/v1/feedback when online.
 */

import { useState, useEffect } from 'react'
import { getPendingFeedbacks, markFeedbackSynced } from './db'
import { getApiUrl } from '../api/config'

export async function syncPendingFeedbacks(): Promise<number> {
  if (!navigator.onLine) {
    return 0
  }

  const pending = await getPendingFeedbacks()
  if (pending.length === 0) {
    return 0
  }

  let syncedCount = 0

  for (const item of pending) {
    try {
      const response = await fetch(getApiUrl('/api/v1/feedback'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          result_id: item.resultId,
          commodity_id: item.commodityId,
          action_taken: item.actionTaken,
          actual_shelf_life_days: item.actualOutcomeDays,
          user_notes: item.notes,
          district: item.district,
          scheduled_followup: item.scheduledFollowUpDate,
        }),
      })

      if (response.ok && item.id !== undefined) {
        await markFeedbackSynced(item.id)
        syncedCount++
      }
    } catch {
      // Network failure, will retry on next online event
      break
    }
  }

  return syncedCount
}

export function initOfflineSync(): () => void {
  const handleOnline = () => {
    syncPendingFeedbacks().catch(() => {})
  }

  window.addEventListener('online', handleOnline)

  // Initial sync attempt if already online
  if (navigator.onLine) {
    syncPendingFeedbacks().catch(() => {})
  }

  return () => {
    window.removeEventListener('online', handleOnline)
  }
}

export function useNetworkStatus(): boolean {
  const [isOnline, setIsOnline] = useState<boolean>(() =>
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  )

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      syncPendingFeedbacks().catch(() => {})
    }
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  return isOnline
}
