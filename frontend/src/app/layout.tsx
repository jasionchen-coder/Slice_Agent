import type { Metadata } from "next";
import Link from "next/link";
import { ActivityIcon, ClapperboardIcon, HistoryIcon, PlusIcon } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "直播切片 Agent",
  description: "直播回放自动分析与短视频切片工具"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-screen">
          <header className="border-b bg-card">
            <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
              <Link href="/" className="flex items-center gap-2 font-semibold">
                <ClapperboardIcon data-icon="inline-start" />
                直播切片 Agent
              </Link>
              <nav className="flex items-center gap-1">
                <Link className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm hover:bg-secondary" href="/">
                  <HistoryIcon data-icon="inline-start" />
                  任务
                </Link>
                <Link className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm hover:bg-secondary" href="/tasks/create">
                  <PlusIcon data-icon="inline-start" />
                  新建
                </Link>
                <Link className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm hover:bg-secondary" href="/system">
                  <ActivityIcon data-icon="inline-start" />
                  状态
                </Link>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}

