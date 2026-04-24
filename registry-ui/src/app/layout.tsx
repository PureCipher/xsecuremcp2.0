import type { Metadata } from "next";
import {
  Geist,
  Geist_Mono,
  JetBrains_Mono,
  Fira_Code,
  IBM_Plex_Mono,
  Source_Code_Pro,
} from "next/font/google";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v16-appRouter";
import "./globals.css";

import { AppThemeRoot } from "@/components/AppThemeRoot";
import { MuiThemeRoot } from "@/components/MuiThemeRoot";
import { DEFAULT_APP_THEME_ID } from "@/lib/appThemes";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-cli-jetbrains-mono",
  subsets: ["latin"],
});

const firaCode = Fira_Code({
  variable: "--font-cli-fira-code",
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-cli-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const sourceCodePro = Source_Code_Pro({
  variable: "--font-cli-source-code-pro",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "PureCipher Secured MCP Registry",
    template: "%s · PureCipher Secured MCP Registry",
  },
  description:
    "Discover trusted MCP tools, manage SecureMCP policy controls, and publish verified listings through PureCipher.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning data-app-theme={DEFAULT_APP_THEME_ID}>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${jetbrainsMono.variable} ${firaCode.variable} ${ibmPlexMono.variable} ${sourceCodePro.variable} antialiased`}
      >
        <AppRouterCacheProvider>
          <AppThemeRoot>
            <MuiThemeRoot>{children}</MuiThemeRoot>
          </AppThemeRoot>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
