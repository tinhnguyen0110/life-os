import { EmptyScreen } from "@/components/EmptyScreen";

// S6 — Portfolio detail (asset breakdown)
export default function PortfolioDetailPage({ params }: { params?: { id?: string } }) {
  const id = params?.id ?? "";
  return <EmptyScreen name={id ? `Danh mục · ${id}` : "Danh mục"} screen="S6" icon="i-pie" />;
}
