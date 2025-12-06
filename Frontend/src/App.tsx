import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import Whales from "./pages/Whales";
import WhaleDetail from "./pages/WhaleDetail";
import LiveFeed from "./pages/LiveFeed";
import Settings from "./pages/Settings";
import About from "./pages/About";
import NotFound from "./pages/NotFound";
import CopierBacktest from "./pages/CopierBacktest";
import LiveCopier from "./pages/LiveCopier";
import MyAccount from "./pages/MyAccount";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/whales" element={<Whales />} />
            <Route path="/whales/:chain/:address" element={<WhaleDetail />} />
            <Route path="/me" element={<MyAccount />} />
            <Route path="/live" element={<LiveFeed />} />
            <Route path="/backtest" element={<CopierBacktest />} />
            <Route path="/copier" element={<LiveCopier />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
