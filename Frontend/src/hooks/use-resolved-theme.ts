import { useEffect, useState } from "react";
import { useUIStore } from "@/stores/uiStore";

type ResolvedTheme = "dark" | "light";

const getSystemTheme = (): ResolvedTheme => {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

export const useResolvedTheme = () => {
  const theme = useUIStore((state) => state.theme);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(getSystemTheme);

  useEffect(() => {
    if (typeof document === "undefined") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const nextTheme = theme === "system" ? (mediaQuery.matches ? "dark" : "light") : theme;
      const root = document.documentElement;

      root.classList.toggle("dark", nextTheme === "dark");
      root.dataset.theme = nextTheme;
      setResolvedTheme(nextTheme === "dark" ? "dark" : "light");
    };

    applyTheme();

    if (theme === "system") {
      mediaQuery.addEventListener("change", applyTheme);
      return () => mediaQuery.removeEventListener("change", applyTheme);
    }

    return () => mediaQuery.removeEventListener("change", applyTheme);
  }, [theme]);

  return resolvedTheme;
};
