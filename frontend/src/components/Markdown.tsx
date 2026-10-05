import { Children, isValidElement, memo, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Check, Copy } from 'lucide-react'
import { copyText } from '../lib/util'
import { useCopied } from './ui'

function nodeText(n: ReactNode): string {
  if (typeof n === 'string' || typeof n === 'number') return String(n)
  if (Array.isArray(n)) return n.map(nodeText).join('')
  if (isValidElement<{ children?: ReactNode }>(n)) return nodeText(n.props.children)
  return ''
}

export function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, mark] = useCopied()
  const code = Children.toArray(children)[0]
  const props = isValidElement<{ className?: string; children?: ReactNode }>(code) ? code.props : {}
  const lang = /language-([\w+#-]+)/.exec(props.className ?? '')?.[1] ?? ''
  const raw = nodeText(props.children).replace(/\n$/, '')
  return (
    <div className="codeblock">
      <div className="flex items-center justify-between border-b border-line px-3 py-1.5 text-xs text-muted">
        <span className="font-mono">{lang || 'text'}</span>
        <button
          type="button"
          onClick={() => void copyText(raw).then(mark)}
          className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 transition-colors duration-150 hover:bg-fg/[0.07] hover:text-fg"
          aria-label={copied ? 'Copied' : `Copy ${lang || 'code'}`}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre tabIndex={0}>{children}</pre>
    </div>
  )
}

const remarkPlugins = [remarkGfm]
const rehypePlugins: NonNullable<Parameters<typeof ReactMarkdown>[0]['rehypePlugins']> = [
  [rehypeHighlight, { detect: false, ignoreMissing: true }],
]
const components: Components = {
  a: ({ href = '', children }) => (
    <a href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  ),
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  table: ({ children }) => (
    <div className="md-table">
      <table>{children}</table>
    </div>
  ),
}

function MarkdownImpl({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={components}>
      {text}
    </ReactMarkdown>
  )
}

export const Markdown = memo(MarkdownImpl)
