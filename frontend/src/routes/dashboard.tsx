import { createFileRoute, Outlet } from "@tanstack/react-router";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [{ title: "Customer Portal — WiseBuys" }],
  }),
  component: DashboardLayout,
});

function DashboardLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <SiteHeader />
      <div className="flex-1 flex flex-col">
        <Outlet />
      </div>
      <SiteFooter />
    </div>
  );
}
