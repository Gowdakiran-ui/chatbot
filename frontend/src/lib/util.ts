import { NOT_LEGAL_ADVICE_LINE, TRUNCATION_NOTICE } from './constants'
import type { Conversation, Message, SourceRef } from './types'

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)

export const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`

export type Group = 'Today' | 'Yesterday' | 'Previous 7 days' | 'Older'
const ORDER: Group[] = ['Today', 'Yesterday', 'Previous 7 days', 'Older']

export function groupConversations(items: Conversation[], now = new Date()): { label: Group; items: Conversation[] }[] {
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const day = 86_400_000
  const buckets = new Map<Group, Conversation[]>()
  for (const c of items) {
    const t = c.updated_at * 1000
    const g: Group = t >= startOfDay ? 'Today' : t >= startOfDay - day ? 'Yesterday' : t >= startOfDay - 7 * day ? 'Previous 7 days' : 'Older'
    buckets.set(g, [...(buckets.get(g) ?? []), c])
  }
  return ORDER.filter((g) => buckets.has(g)).map((label) => ({ label, items: buckets.get(label)! }))
}

export function deriveTitle(messages: Message[]): string {
  const first = messages.find((m) => m.role === 'user')?.content.trim().replace(/\s+/g, ' ') ?? ''
  if (!first) return 'New chat'
  return first.length > 48 ? `${first.slice(0, 47).trimEnd()}…` : first
}

export interface AnswerParts {
  body: string
  truncated: boolean
  disclaimer: boolean
}

/**
 * The backend appends two literal strings to some answers (truncation notice, crisis not-legal-advice line).
 * Lift them out of the flowing text so the UI can render them as their own elements.
 */
export function splitAnswer(content: string): AnswerParts {
  let body = content
  let truncated = false
  let disclaimer = false
  if (body.includes(TRUNCATION_NOTICE)) {
    truncated = true
    body = body.replace(TRUNCATION_NOTICE, '')
  }
  if (body.includes(NOT_LEGAL_ADVICE_LINE)) {
    disclaimer = true
    body = body.replace(NOT_LEGAL_ADVICE_LINE, '')
  }
  return { body: body.trim(), truncated, disclaimer }
}

/** Crisis metadata can be a full sentence; chips show a short form and keep the full text in the tooltip. */
export const CHIP_MAX = 44

/** Small descriptive tags for a source: domain tags (Chanakya) or crisis type / industry / resolution (Crisis). */
export function chipsFor(s: SourceRef): string[] {
  const out: string[] = []
  for (const key of ['domain_tags', 'crisis_type', 'industry', 'resolution_status']) {
    const v = s.metadata?.[key]
    const vals = Array.isArray(v) ? v : [v]
    for (const x of vals) if (typeof x === 'string' && x.trim()) out.push(x.trim().replace(/_/g, ' '))
  }
  return [...new Set(out)]
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}
