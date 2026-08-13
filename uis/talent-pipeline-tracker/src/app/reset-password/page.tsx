import ResetPasswordForm from "@/components/ResetPasswordForm";

export default function ResetPasswordPage({ searchParams }: { searchParams: { token?: string } }) {
  return <ResetPasswordForm token={searchParams.token ?? ""} />;
}
