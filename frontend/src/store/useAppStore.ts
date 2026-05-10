import { create } from "zustand"

interface AppState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  theme: "light" | "dark"
  toggleTheme: () => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  theme: "light",
  toggleTheme: () => set((state) => ({ theme: state.theme === "light" ? "dark" : "light" })),
}))
