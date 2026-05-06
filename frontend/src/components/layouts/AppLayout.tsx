import { Outlet } from "react-router-dom"

export function AppLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Outlet />
    </div>
  );
}
