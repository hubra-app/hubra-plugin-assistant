import { apiFetch } from '@hubra/plugin-sdk'

export type Kind = 'post' | 'invitation' | 'reminder' | 'minutes' | 'other'
export const KINDS: Kind[] = ['post', 'invitation', 'reminder', 'minutes', 'other']
export type Language = 'de' | 'fr' | 'it' | 'en'
export const LANGUAGES: Language[] = ['de', 'fr', 'it', 'en']
export type Length = 'short' | 'medium' | 'long'

export interface Options {
  ready: boolean
  consent: boolean
  hasKey: boolean
  model: string
  address: 'du' | 'sie'
  tone: string
  events: { id: number; title: string; date: string }[]
}

export interface Draft {
  id: number
  kind: Kind
  language: Language
  notes: string
  eventId: number | null
  title: string | null
  body: string | null
  model: string
  tokens: number
  createdAt: string | null
}

export const QK = {
  options: ['assistant', 'options'] as const,
  drafts: ['assistant', 'drafts'] as const,
}

const BASE = '/app/assistant'

export const getOptions = () => apiFetch<Options>(`${BASE}/options`)
export const listDrafts = () => apiFetch<Draft[]>(`${BASE}/drafts`)
export const createDraft = (body: { kind: Kind; language: Language; length: Length; notes: string; eventId: number | null }) =>
  apiFetch<Draft>(`${BASE}/drafts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
export const deleteDraft = (id: number) => apiFetch<void>(`${BASE}/drafts/${id}`, { method: 'DELETE' })

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}
