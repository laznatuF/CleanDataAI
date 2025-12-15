// frontend/src/App.tsx
import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Home from "../src/api/pages/Home";
import StatusPage from "../src/api/pages/Status";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/status/:id" element={<StatusPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
