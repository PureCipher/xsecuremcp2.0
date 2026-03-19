export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[--app-accent] border-t-transparent" />
      <p className="mt-3 text-[11px] text-[--app-muted]">{message}</p>
    </div>
  );
}
