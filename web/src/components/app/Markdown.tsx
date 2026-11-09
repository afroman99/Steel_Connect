import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

// AI 답변(마크다운)을 그린다. 표·목록·굵은 글씨·코드를 지원한다(이전 화면은 표가 깨졌다).
export function Markdown({ children }: { children: string }) {
  return (
    <div className="space-y-3 text-base leading-7">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <p className="font-semibold" {...p} />,
          h2: (p) => <p className="pt-1 font-semibold" {...p} />,
          h3: (p) => <p className="font-semibold" {...p} />,
          ul: (p) => <ul className="list-disc space-y-1 pl-6" {...p} />,
          ol: (p) => <ol className="list-decimal space-y-1 pl-6" {...p} />,
          code: (p) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm" {...p} />,
          table: (p) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm" {...p} />
            </div>
          ),
          th: (p) => <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground" {...p} />,
          td: (p) => <td className="border-b border-border/60 px-3 py-2 align-top" {...p} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
