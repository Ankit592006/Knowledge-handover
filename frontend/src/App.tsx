import React from "react";
import { AuthProvider } from "./hooks/useAuth";
import { PlatformWorkspace } from "./pages/PlatformWorkspace";

export function App() {
  return (
    <AuthProvider>
      <PlatformWorkspace />
    </AuthProvider>
  );
}

export default App;
