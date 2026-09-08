import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownContent({ children }: { children: string }) {
  return <div className="markdown-content">
    <Markdown remarkPlugins={[remarkGfm]} skipHtml disallowedElements={["img"]}
      components={{ a: ({ children, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer">{children}</a> }}>
      {children}
    </Markdown>
  </div>;
}
