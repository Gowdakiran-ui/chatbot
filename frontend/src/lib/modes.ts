import type { LucideIcon } from 'lucide-react'
import { Compass, Handshake, Landmark, Megaphone, Newspaper, Scale, ShieldAlert, Users } from 'lucide-react'
import type { Mode } from './types'

export interface ModeConfig {
  label: string
  /** short tag shown on sidebar rows */
  tag: string
  /** one line shown in the mode picker */
  blurb: string
  title: string
  description: string
  placeholder: string
  starters: { icon: LucideIcon; text: string }[]
}

export const MODES: Record<Mode, ModeConfig> = {
  chanakya: {
    label: 'Chanakya',
    tag: 'Chanakya',
    blurb: 'Career, leadership and ethics advice from the Arthashastra and Chanakya Niti.',
    title: 'What counsel do you seek?',
    description:
      'Practical advice on career, leadership and ethics, drawn from the Arthashastra and Chanakya Niti and restated for modern business.',
    placeholder: 'Ask Chanakya for counsel…',
    starters: [
      { icon: Users, text: 'How should a new manager earn the trust of a team that was passed over for the role?' },
      { icon: Landmark, text: 'How should a leader choose advisors, and whom should they trust?' },
      { icon: Handshake, text: 'When should I negotiate, and when should I hold firm?' },
      { icon: Scale, text: 'How should a leader respond when a trusted employee makes a serious mistake?' },
    ],
  },
  crisis: {
    label: 'Crisis Advisor',
    tag: 'Crisis',
    blurb: 'Precedent-based guidance from past PR and reputation crises.',
    title: "What's the situation?",
    description: 'Precedent-based guidance from past PR and reputation crises: what worked, what did not, and why.',
    placeholder: 'Describe the situation…',
    starters: [
      { icon: Megaphone, text: "A founder's old posts have resurfaced and are trending. What precedent exists for responding?" },
      { icon: ShieldAlert, text: 'A data breach exposed customer records. How have other companies handled the first 48 hours?' },
      { icon: Newspaper, text: 'An executive scandal has hit the news. How did companies rebuild trust afterwards?' },
      { icon: Compass, text: 'Negative reviews are being posted in a coordinated campaign. What worked in similar cases?' },
    ],
  },
}

export const MODE_ORDER: Mode[] = ['chanakya', 'crisis']

export const SINGLE_TURN_HINT = 'Each question is answered on its own.'
export const SINGLE_TURN_DETAIL = 'Each question is answered on its own; earlier messages in the chat are not used as context.'
