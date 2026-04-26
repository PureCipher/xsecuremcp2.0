import { Box, Typography } from "@mui/material";

type Props = {
  defaultMcpUrl: string;
  allowedOrigin: string;
  className?: string;
};

export function CliCheatsheet({ defaultMcpUrl, allowedOrigin, className = "" }: Props) {
  return (
    <Box
      component="aside"
      className={className}
      sx={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "min(720px, calc(100vh - 10rem))",
        overflowY: "auto",
        border: "1px solid var(--app-border)",
        borderRadius: 0,
        bgcolor: "var(--app-surface)",
        p: 0,
        boxShadow: "0 24px 70px rgba(15, 23, 42, 0.08)",
      }}
    >
      <Box sx={{ p: 2.25, borderBottom: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Command palette
        </Typography>
        <Typography sx={{ mt: 0.75, fontSize: 13, fontWeight: 750, color: "var(--app-fg)" }}>
          Quick MCP actions
        </Typography>
        <Typography variant="caption" sx={{ mt: 0.75, display: "block", color: "var(--app-muted)", lineHeight: 1.6 }}>
          Shortcuts use your registry MCP endpoint automatically. Only{" "}
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-fg)" }}>
            {allowedOrigin}
          </Box>{" "}
          is allowed.
        </Typography>
      </Box>

      <Box sx={{ p: 2.25 }}>
      <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
        First commands
      </Typography>
      <Box
        component="ul"
        sx={{
          mt: 1,
          display: "grid",
          gap: 1,
          listStyle: "none",
          p: 0,
          m: 0,
          fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          color: "var(--app-fg)",
          fontSize: 11,
        }}
      >
        <CheatsheetRow comment="Tools only" cmd="list" />
        <CheatsheetRow comment="Tools + prompts" cmd="list --prompts" />
        <CheatsheetRow comment="Machine-readable" cmd="list --prompts --json" />
        <CheatsheetRow comment="Invoke tool" cmd="call registry_status" />
        <CheatsheetRow comment="Admin only" cmd="admin status" />
        <CheatsheetRow comment="Prompt" cmd='call my_prompt --prompt topic=SecureMCP' />
      </Box>

      <Typography variant="overline" sx={{ mt: 2, color: "var(--app-muted)", letterSpacing: "0.16em" }}>
        Admin commands
      </Typography>
      <Box
        component="ul"
        sx={{
          mt: 1,
          display: "grid",
          gap: 1,
          listStyle: "none",
          p: 0,
          m: 0,
          fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          color: "var(--app-fg)",
          fontSize: 11,
        }}
      >
        <CheatsheetRow comment="Session + health" cmd="admin status" />
        <CheatsheetRow comment="Health JSON" cmd="admin health" />
        <CheatsheetRow comment="Review counts" cmd="admin queue" />
        <CheatsheetRow comment="Policy snapshot" cmd="admin policy" />
        <CheatsheetRow comment="Account events" cmd="admin activity" />
      </Box>

      <Typography variant="overline" sx={{ mt: 2, color: "var(--app-muted)", letterSpacing: "0.16em" }}>
        Explicit URL
      </Typography>
      <Typography
        variant="caption"
        sx={{
          mt: 0.5,
          display: "block",
          color: "var(--app-muted)",
          wordBreak: "break-word",
          fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: 10,
          lineHeight: 1.6,
        }}
      >
        securemcp list {defaultMcpUrl} --prompts
      </Typography>

      <Typography variant="overline" sx={{ mt: 2, color: "var(--app-muted)", letterSpacing: "0.16em" }}>
        Help
      </Typography>
      <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
        <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-fg)" }}>
          help
        </Box>{" "}
        or{" "}
        <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-fg)" }}>
          commands
        </Box>{" "}
        - full reference
      </Typography>

      <Typography variant="overline" sx={{ mt: 2, color: "var(--app-muted)", letterSpacing: "0.16em" }}>
        Keys
      </Typography>
      <Box component="ul" sx={{ mt: 0.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
        <li>Up / Down - command history</li>
        <li>Ctrl+C - cancel current line</li>
        <li>
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            clear
          </Box>{" "}
          - wipe screen and banner
        </li>
      </Box>
      </Box>

      <Box sx={{ mt: "auto", borderTop: "1px solid var(--app-border)", p: 2.25, bgcolor: "var(--app-control-bg)" }}>
        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
          Theme and font size persist in this browser.
        </Typography>
      </Box>
    </Box>
  );
}

function CheatsheetRow({ comment, cmd }: { comment: string; cmd: string }) {
  return (
    <Box
      component="li"
      sx={{
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        borderRadius: 0,
        px: 1.5,
        py: 1.25,
      }}
    >
      <Box component="span" sx={{ color: "var(--app-muted)" }}>
        # {comment}
      </Box>
      <Box component="div" sx={{ mt: 0.5, color: "var(--app-fg)" }}>
        {cmd}
      </Box>
    </Box>
  );
}
