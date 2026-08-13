import CandidateForm from "@/components/CandidateForm";

export default async function EditCandidatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CandidateForm mode="edit" recordId={id} />;
}
