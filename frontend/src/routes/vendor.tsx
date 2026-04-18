import { createFileRoute, Outlet } from "@tanstack/react-router";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";

export const Route = createFileRoute("/vendor")({
  head: () => ({
    meta: [{ title: "Vendor — WiseBuys" }],
  }),
  component: VendorLayout,
});

function VendorLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-cream">
      <SiteHeader />
      <div className="flex-1 flex flex-col">
        <Outlet />
      </div>
      <SiteFooter />
    </div>
  );
}
