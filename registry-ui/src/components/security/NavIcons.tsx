type Props = {
  name:
    | "tools"
    | "publish"
    | "publishers"
    | "review"
    | "policy"
    | "provenance"
    | "contracts"
    | "consent"
    | "reflexive"
    | "cli"
    | "servers"
    | "clients"
    | "access"
    | "health"
    | "settings";
  className?: string;
};

export function NavIcon({ name, className = "h-4 w-4" }: Props) {
  const common = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    xmlns: "http://www.w3.org/2000/svg",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  } as const;

  switch (name) {
    case "tools":
      return (
        <svg {...common}>
          <path d="M14.7 6.3a4 4 0 0 1-5.4 5.4L4 17l3 3 5.3-5.3a4 4 0 0 1 5.4-5.4l-1.8 1.8-2.2-.6-.6-2.2L14.7 6.3Z" />
        </svg>
      );
    case "publish":
      return (
        <svg {...common}>
          <path d="M12 3v12" />
          <path d="M7 8l5-5 5 5" />
          <path d="M5 21h14" />
        </svg>
      );
    case "publishers":
      return (
        <svg {...common}>
          <path d="M16 11a4 4 0 1 0-8 0" />
          <path d="M4 21a8 8 0 0 1 16 0" />
          <path d="M20 21a8 8 0 0 0-6.2-7.8" />
        </svg>
      );
    case "review":
      return (
        <svg {...common}>
          <path d="M9 11l2 2 4-4" />
          <path d="M7 4h10v16H7z" />
        </svg>
      );
    case "policy":
      return (
        <svg {...common}>
          <path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4Z" />
          <path d="M9.5 12.5h5" />
          <path d="M9.5 9.5h5" />
        </svg>
      );
    case "provenance":
      return (
        <svg {...common}>
          <path d="M8 7h12" />
          <path d="M4 7h.01" />
          <path d="M8 12h12" />
          <path d="M4 12h.01" />
          <path d="M8 17h12" />
          <path d="M4 17h.01" />
        </svg>
      );
    case "contracts":
      return (
        <svg {...common}>
          <path d="M8 7h8" />
          <path d="M8 11h8" />
          <path d="M8 15h5" />
          <path d="M6 3h12a2 2 0 0 1 2 2v14l-4-2-4 2-4-2-4 2V5a2 2 0 0 1 2-2Z" />
        </svg>
      );
    case "consent":
      return (
        <svg {...common}>
          <path d="M12 21s7-4.5 7-10V6l-7-3-7 3v5c0 5.5 7 10 7 10Z" />
          <path d="M9 12l2 2 4-4" />
        </svg>
      );
    case "reflexive":
      return (
        <svg {...common}>
          <path d="M12 19c4 0 7-3 7-7s-3-7-7-7-7 3-7 7 3 7 7 7Z" />
          <path d="M12 9v3l2 2" />
        </svg>
      );
    case "cli":
      return (
        <svg {...common}>
          <path d="M4 6h16v12H4z" />
          <path d="M8 10l2 2-2 2" />
          <path d="M12 14h4" />
        </svg>
      );
    case "servers":
      return (
        <svg {...common}>
          <path d="M4 7h16v4H4z" />
          <path d="M4 13h16v4H4z" />
          <path d="M8 9h.01" />
          <path d="M8 15h.01" />
        </svg>
      );
    case "clients":
      return (
        <svg {...common}>
          <path d="M16 11c0 2.2-1.8 4-4 4s-4-1.8-4-4 1.8-4 4-4 4 1.8 4 4Z" />
          <path d="M4.5 21c1.2-3.5 4-5 7.5-5s6.3 1.5 7.5 5" />
        </svg>
      );
    case "access":
      return (
        <svg {...common}>
          <path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4Z" />
          <path d="M9 12h6" />
          <path d="M12 9v6" />
        </svg>
      );
    case "health":
      return (
        <svg {...common}>
          <path d="M12 21s-7-4.5-7-10V6l7-3 7 3v5c0 5.5-7 10-7 10Z" />
          <path d="M8 12h2l1-2 2 4 1-2h2" />
        </svg>
      );
    case "settings":
      return (
        <svg {...common}>
          <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
          <path d="M19.4 15a7.7 7.7 0 0 0 .1-2l2-1.2-2-3.4-2.3.6a7.9 7.9 0 0 0-1.7-1L15.2 4h-6.4L8.5 7.9a7.9 7.9 0 0 0-1.7 1l-2.3-.6-2 3.4 2 1.2a7.7 7.7 0 0 0 .1 2l-2 1.2 2 3.4 2.3-.6a7.9 7.9 0 0 0 1.7 1l.3 2.9h6.4l.3-2.9a7.9 7.9 0 0 0 1.7-1l2.3.6 2-3.4-2-1.2Z" />
        </svg>
      );
    default:
      return null;
  }
}

