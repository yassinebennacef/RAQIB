import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/noto-kufi-arabic/arabic-500.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { Layout } from "@/components/Layout";
import About from "@/pages/About";
import ControlRoom from "@/pages/ControlRoom";
import Inspector from "@/pages/Inspector";
import ModelLab from "@/pages/ModelLab";
import NotFound from "@/pages/NotFound";
import TryDeclaration from "@/pages/TryDeclaration";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ControlRoom />} />
          <Route path="declaration/:id" element={<Inspector />} />
          <Route path="score" element={<TryDeclaration />} />
          <Route path="lab" element={<ModelLab />} />
          <Route path="about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
    <Toaster theme="dark" position="bottom-right" richColors closeButton />
  </StrictMode>,
);
