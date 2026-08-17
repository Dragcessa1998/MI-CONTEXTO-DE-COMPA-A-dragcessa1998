import AuthForm from "@/components/AuthForm";

export default function LoginPage({ searchParams }: { searchParams: { reset?: string } }) {
  return <AuthForm mode="login" resetSuccess={searchParams.reset === "success"} />;
}
