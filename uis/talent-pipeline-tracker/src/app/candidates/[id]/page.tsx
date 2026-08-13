import CandidateDetail from "@/components/CandidateDetail";

export default async function CandidateDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ saved?: string }>;
}) {
  const { id } = await params;
  const { saved } = await searchParams;
  const savedState = saved === "created" || saved === "updated" ? saved : undefined;
  return <CandidateDetail id={id} saved={savedState} />;
}
