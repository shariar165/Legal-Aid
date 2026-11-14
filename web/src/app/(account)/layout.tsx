/* Sign-in screens share the Counsel workspace look (English-first); the root layout loads the faces. */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return <div lang="en">{children}</div>;
}
