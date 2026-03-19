import Link from "next/link";

type Props = {
  defaultMcpUrl: string;
  allowedOrigin: string;
  className?: string;
};

export function CliCheatsheet({ defaultMcpUrl, allowedOrigin, className = "" }: Props) {
  return (
    <aside
      className={`flex max-h-[min(720px,calc(100vh-10rem))] flex-col overflow-y-auto border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring] ${className}`}
    >
      <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">Cheatsheet</h2>
      <p className="mt-2 text-[11px] leading-relaxed text-[--app-muted]">
        Shortcuts use your{" "}
        <span className="font-mono text-[--app-fg]">REGISTRY_BACKEND_URL</span> MCP endpoint automatically. Only{" "}
        <span className="font-mono text-[--app-fg]">{allowedOrigin}</span> is allowed.
      </p>

      <h3 className="mt-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">First commands</h3>
      <ul className="mt-2 grid gap-2 font-mono text-[11px] text-[--app-fg]">
        <CheatsheetRow comment="Tools only" cmd="list" />
        <CheatsheetRow comment="Tools + prompts" cmd="list --prompts" />
        <CheatsheetRow comment="Machine-readable" cmd="list --prompts --json" />
        <CheatsheetRow comment="Invoke tool" cmd="call registry_status" />
        <CheatsheetRow comment="Prompt" cmd='call my_prompt --prompt topic=SecureMCP' />
      </ul>

      <h3 className="mt-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">Explicit URL</h3>
      <p className="mt-1 break-all font-mono text-[10px] leading-relaxed text-[--app-muted]">
        securemcp list {defaultMcpUrl} --prompts
      </p>

      <h3 className="mt-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">Help</h3>
      <p className="mt-1 text-[11px] text-[--app-muted]">
        <span className="font-mono text-[--app-fg]">help</span> or{" "}
        <span className="font-mono text-[--app-fg]">commands</span> — full reference
      </p>

      <h3 className="mt-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">Keys</h3>
      <ul className="mt-1 list-inside list-disc text-[11px] text-[--app-muted]">
        <li>↑ / ↓ — command history</li>
        <li>Ctrl+C — cancel current line</li>
        <li>
          <span className="font-mono">clear</span> — wipe screen & banner
        </li>
      </ul>

      <div className="mt-auto border-t border-[--app-border] pt-4">
        <p className="text-[10px] text-[--app-muted]">
          Theme & font size persist in{" "}
          <Link href="/registry/settings#browser-cli-terminal" className="underline decoration-[--app-accent]">
            Settings
          </Link>
          .
        </p>
      </div>
    </aside>
  );
}

function CheatsheetRow({ comment, cmd }: { comment: string; cmd: string }) {
  return (
    <li className="border border-[--app-border] bg-[--app-control-bg] px-2.5 py-2 ring-1 ring-[--app-surface-ring]">
      <span className="text-[--app-muted]"># {comment}</span>
      <div className="mt-0.5 text-[--app-fg]">{cmd}</div>
    </li>
  );
}
