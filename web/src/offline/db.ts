/**
 * Aavaran Offline IndexedDB Store.
 * Provides caching for commodity profiles, films, rules, and queued outcome feedback.
 */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb'

export interface FeedbackSubmission {
  id?: number
  resultId: string
  commodityId: string
  actionTaken: string
  actualOutcomeDays?: number
  notes?: string
  district?: string
  scheduledFollowUpDate: string
  createdAt: string
  synced: boolean
}

export interface AavaranDB extends DBSchema {
  commodities: {
    key: string
    value: {
      commodity_id: string
      name: string
      names: Record<string, string[]>
      group: string
      class: string
      physchem: Record<string, unknown>
      respiration?: Record<string, unknown>
      storage_optimum?: Record<string, unknown>
      failure_modes: string[]
    }
  }
  films: {
    key: string
    value: {
      id: string
      film_name: string
      thickness_um: number
      otr_value: number
      wvtr_value: number
      epr_category: string
    }
  }
  rules: {
    key: string
    value: {
      id: string
      title: string
      severity: string
    }
  }
  feedback_queue: {
    key: number
    value: FeedbackSubmission
    indexes: { 'by-synced': number }
  }
}

const DB_NAME = 'aavaran-offline-db'
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<AavaranDB>> | null = null

export function getDB(): Promise<IDBPDatabase<AavaranDB>> {
  if (!dbPromise) {
    dbPromise = openDB<AavaranDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('commodities')) {
          db.createObjectStore('commodities', { keyPath: 'commodity_id' })
        }
        if (!db.objectStoreNames.contains('films')) {
          db.createObjectStore('films', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('rules')) {
          db.createObjectStore('rules', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('feedback_queue')) {
          const store = db.createObjectStore('feedback_queue', {
            keyPath: 'id',
            autoIncrement: true,
          })
          store.createIndex('by-synced', 'synced')
        }
      },
    })
  }
  return dbPromise
}

export async function queueFeedback(
  feedback: Omit<FeedbackSubmission, 'id' | 'synced' | 'createdAt'>,
): Promise<number> {
  const db = await getDB()
  const entry: FeedbackSubmission = {
    ...feedback,
    createdAt: new Date().toISOString(),
    synced: false,
  }
  const id = await db.add('feedback_queue', entry)
  return id
}

export async function getPendingFeedbacks(): Promise<FeedbackSubmission[]> {
  const db = await getDB()
  const all = await db.getAll('feedback_queue')
  return all.filter((item) => !item.synced)
}

export async function markFeedbackSynced(id: number): Promise<void> {
  const db = await getDB()
  const item = await db.get('feedback_queue', id)
  if (item) {
    item.synced = true
    await db.put('feedback_queue', item)
  }
}
