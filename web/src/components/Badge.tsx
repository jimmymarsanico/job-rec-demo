interface BadgeProps {
  children: React.ReactNode;
  variant?:
    | "default"
    | "blue"
    | "green"
    | "orange"
    | "purple"
    | "remote"
    | "hybrid"
    | "onsite";
  title?: string;
}

const variantClasses: Record<string, string> = {
  default: "bg-gray-100 text-gray-700",
  blue: "bg-blue-100 text-blue-700",
  green: "bg-emerald-100 text-emerald-700",
  orange: "bg-orange-100 text-orange-700",
  purple: "bg-purple-100 text-purple-700",
  remote: "bg-teal-100 text-teal-700",
  hybrid: "bg-violet-100 text-violet-700",
  onsite: "bg-amber-100 text-amber-800",
};

/** Map a workplace value to its badge variant. */
export function workplaceVariant(workplace: string): BadgeProps["variant"] {
  if (workplace === "Remote") return "remote";
  if (workplace === "Hybrid") return "hybrid";
  return "onsite";
}

export default function Badge({ children, variant = "default", title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${variantClasses[variant]}`}
    >
      {children}
    </span>
  );
}
