import { EmptyScreen } from "@/components/EmptyScreen";

// S3 — Project Detail
export default function ProjectDetailPage({ params }: { params?: { id?: string } }) {
  const id = params?.id ?? "";
  return <EmptyScreen name={id ? `Dự án · ${id}` : "Dự án"} screen="S3" icon="i-proj" />;
}
