import { describe, expect, it } from 'vitest'
import { NOT_LEGAL_ADVICE_LINE, TRUNCATION_NOTICE } from '../constants'
import { parseFrame } from '../api'
import { chipsFor, deriveTitle, groupConversations, splitAnswer } from '../util'
import type { Conversation, Message } from '../types'

describe('parseFrame (SSE)', () => {
  it('parses token, final and error frames', () => {
    expect(parseFrame('data: {"type":"token","text":"hi"}')).toEqual({ type: 'token', text: 'hi' })
    expect(parseFrame('data: {"type":"final","refused":false}')?.type).toBe('final')
    expect(parseFrame('data: {"type":"error","message":"x"}')?.type).toBe('error')
  })
  it('ignores comments, malformed JSON and frames without a type', () => {
    expect(parseFrame(': keep-alive')).toBeNull()
    expect(parseFrame('data: {oops')).toBeNull()
    expect(parseFrame('data: {"text":"no type"}')).toBeNull()
    expect(parseFrame('data: 42')).toBeNull()
  })
})

describe('splitAnswer', () => {
  it('lifts out the truncation notice and the legal line', () => {
    const r = splitAnswer(`Answer text.\n\n${TRUNCATION_NOTICE}\n\n${NOT_LEGAL_ADVICE_LINE}`)
    expect(r).toEqual({ body: 'Answer text.', truncated: true, disclaimer: true })
  })
  it('leaves ordinary answers alone', () => {
    expect(splitAnswer('Plain.')).toEqual({ body: 'Plain.', truncated: false, disclaimer: false })
  })
})

describe('chipsFor', () => {
  it('reads Chanakya domain tags and Crisis metadata, de-duplicated and de-underscored', () => {
    expect(chipsFor({ id: 'a', label: 'A', snippet: '', metadata: { domain_tags: ['ethics', 'ethics', 'war_craft'] } })).toEqual(['ethics', 'war craft'])
    expect(chipsFor({ id: 'b', label: 'B', snippet: '', metadata: { crisis_type: 'Breach', industry: 'Retail', resolution_status: 'Resolved' } })).toEqual(['Breach', 'Retail', 'Resolved'])
    expect(chipsFor({ id: 'c', label: 'C', snippet: '', metadata: {} })).toEqual([])
  })
})

describe('conversation helpers', () => {
  const msg = (content: string): Message => ({ uid: 'u', role: 'user', content })
  it('derives a short title from the first user message', () => {
    expect(deriveTitle([])).toBe('New chat')
    expect(deriveTitle([msg('  hello   world ')])).toBe('hello world')
    expect(deriveTitle([msg('x'.repeat(100))]).length).toBe(48)
  })
  it('groups by recency', () => {
    const now = new Date('2026-10-05T12:00:00')
    const c = (id: string, ageDays: number): Conversation => ({ id, title: id, mode: 'chanakya', created_at: 0, updated_at: now.getTime() / 1000 - ageDays * 86400, messages: [] })
    const groups = groupConversations([c('a', 0), c('b', 1), c('c', 3), c('d', 30)], now)
    expect(groups.map((g) => g.label)).toEqual(['Today', 'Yesterday', 'Previous 7 days', 'Older'])
  })
})
